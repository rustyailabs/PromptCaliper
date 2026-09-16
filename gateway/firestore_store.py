"""Firestore persistence helpers for PromptCaliper.

The gateway keeps its public API objects shaped like the previous SQLAlchemy
models, but persistence now goes through Firestore using ADC and the named
database configured by FIRESTORE_DATABASE.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from urllib.parse import quote

import google.auth
from google.auth.transport.requests import Request as GoogleAuthRequest
import requests

from gateway.config import settings

logger = logging.getLogger(__name__)

SCOPES = ("https://www.googleapis.com/auth/cloud-platform",)
_READ_CACHE_TTL_SECONDS = 8.0


COLLECTIONS = {
    "admin_users",
    "refresh_token_blocklist",
    "system_config",
    "guardrail_configs",
    "virtual_keys",
    "cache_configs",
    "model_configs",
    "teams",
    "budget_policies",
    "rate_limit_policies",
    "request_logs",
    "spend_ledger",
    "alert_rules",
    "alert_events",
}


class FirestoreObject(SimpleNamespace):
    """Attribute-access object that serializes cleanly via Pydantic from_attributes."""

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self._dirty: set[str] = set()

    def __setattr__(self, name: str, value: Any) -> None:
        super().__setattr__(name, value)
        if not name.startswith("_") and hasattr(self, "_dirty"):
            self._dirty.add(name)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_plain(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, FirestoreObject):
        return {
            k: to_plain(v)
            for k, v in vars(value).items()
            if not k.startswith("_")
        }
    if isinstance(value, list):
        return [to_plain(v) for v in value]
    if isinstance(value, dict):
        return {k: to_plain(v) for k, v in value.items()}
    return value


def from_plain(value: Any) -> Any:
    if isinstance(value, str):
        try:
            if "T" in value and (value.endswith("+00:00") or value.endswith("Z")):
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
    if isinstance(value, list):
        return [from_plain(v) for v in value]
    if isinstance(value, dict):
        return {k: from_plain(v) for k, v in value.items()}
    return value


def object_from(collection: str, data: dict[str, Any] | None) -> FirestoreObject | None:
    if data is None:
        return None
    obj = FirestoreObject(**{k: from_plain(v) for k, v in data.items()})
    obj._collection = collection
    obj._dirty.clear()
    return obj


class FirestoreStore:
    def __init__(self) -> None:
        project = settings.FIRESTORE_PROJECT or settings.VERTEXAI_PROJECT
        if not project:
            raise RuntimeError("FIRESTORE_PROJECT or VERTEXAI_PROJECT must be set for Firestore storage.")
        self.project = project
        self.database = settings.FIRESTORE_DATABASE
        self._credentials = None
        self._lock = threading.Lock()
        self._session = requests.Session()
        self._read_cache: dict[tuple[Any, ...], tuple[float, Any]] = {}
        self.base_url = (
            "https://firestore.googleapis.com/v1/projects/"
            f"{quote(self.project)}/databases/{quote(self.database)}/documents"
        )

    def _cache_get(self, key: tuple[Any, ...]) -> Any | None:
        entry = self._read_cache.get(key)
        if entry and time.monotonic() < entry[0]:
            return entry[1]
        return None

    def _cache_set(self, key: tuple[Any, ...], value: Any) -> None:
        self._read_cache[key] = (time.monotonic() + _READ_CACHE_TTL_SECONDS, value)

    def _invalidate_collection(self, collection: str) -> None:
        stale = [k for k in self._read_cache if k[0] == collection]
        for key in stale:
            del self._read_cache[key]

    def _headers(self) -> dict[str, str]:
        with self._lock:
            if self._credentials is None:
                self._credentials, _ = google.auth.default(scopes=SCOPES)
            if not self._credentials.valid:
                self._credentials.refresh(GoogleAuthRequest())
            return {"Authorization": f"Bearer {self._credentials.token}"}

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        headers = kwargs.pop("headers", {})
        headers.update(self._headers())
        response = self._session.request(method, url, headers=headers, timeout=30, **kwargs)
        if response.status_code >= 400:
            logger.error("Firestore %s %s failed: %s", method, url, response.text)
            response.raise_for_status()
        return response

    def _doc_url(self, collection: str, doc_id: str | int) -> str:
        return f"{self.base_url}/{quote(collection)}/{quote(str(doc_id))}"

    def _col_url(self, collection: str) -> str:
        return f"{self.base_url}/{quote(collection)}"

    def _encode_value(self, value: Any) -> dict[str, Any]:
        value = to_plain(value)
        if value is None:
            return {"nullValue": None}
        if isinstance(value, bool):
            return {"booleanValue": value}
        if isinstance(value, int):
            return {"integerValue": str(value)}
        if isinstance(value, float):
            return {"doubleValue": value}
        if isinstance(value, str):
            return {"stringValue": value}
        if isinstance(value, list):
            return {"arrayValue": {"values": [self._encode_value(v) for v in value]}}
        if isinstance(value, dict):
            return {"mapValue": {"fields": {k: self._encode_value(v) for k, v in value.items()}}}
        return {"stringValue": str(value)}

    def _decode_value(self, value: dict[str, Any]) -> Any:
        if "nullValue" in value:
            return None
        if "booleanValue" in value:
            return value["booleanValue"]
        if "integerValue" in value:
            return int(value["integerValue"])
        if "doubleValue" in value:
            return value["doubleValue"]
        if "stringValue" in value:
            return from_plain(value["stringValue"])
        if "timestampValue" in value:
            return from_plain(value["timestampValue"])
        if "arrayValue" in value:
            return [self._decode_value(v) for v in value["arrayValue"].get("values", [])]
        if "mapValue" in value:
            return {k: self._decode_value(v) for k, v in value["mapValue"].get("fields", {}).items()}
        return None

    def _encode_doc(self, data: dict[str, Any]) -> dict[str, Any]:
        return {"fields": {k: self._encode_value(v) for k, v in data.items() if not k.startswith("_")}}

    def _decode_doc(self, collection: str, raw: dict[str, Any]) -> FirestoreObject:
        data = {k: self._decode_value(v) for k, v in raw.get("fields", {}).items()}
        if "id" not in data:
            data["id"] = raw.get("name", "").rsplit("/", 1)[-1]
        return object_from(collection, data)

    def next_id(self, collection: str) -> int:
        url = self._doc_url("_counters", collection)
        try:
            current = self.get("_counters", collection)
            next_value = int(getattr(current, "value", 0)) + 1 if current else 1
        except Exception:
            next_value = 1
        self.set("_counters", collection, {"id": collection, "value": next_value})
        return next_value

    def set(self, collection: str, doc_id: str | int, data: dict[str, Any]) -> FirestoreObject:
        data = dict(data)
        now = utcnow()
        data.setdefault("id", int(doc_id) if str(doc_id).isdigit() else str(doc_id))
        data.setdefault("created_at", now)
        data["updated_at"] = now
        self._request("PATCH", self._doc_url(collection, doc_id), json=self._encode_doc(data))
        self._invalidate_collection(collection)
        return object_from(collection, data)

    def create(self, collection: str, data: dict[str, Any], doc_id: str | int | None = None) -> FirestoreObject:
        doc_id = doc_id if doc_id is not None else self.next_id(collection)
        return self.set(collection, doc_id, data)

    def get(self, collection: str, doc_id: str | int) -> FirestoreObject | None:
        cache_key = (collection, "get", str(doc_id))
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        response = self._session.get(self._doc_url(collection, doc_id), headers=self._headers(), timeout=30)
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            logger.error("Firestore get failed: %s", response.text)
            response.raise_for_status()
        doc = self._decode_doc(collection, response.json())
        self._cache_set(cache_key, doc)
        return doc

    def delete(self, collection: str, doc_id: str | int) -> None:
        response = self._session.delete(self._doc_url(collection, doc_id), headers=self._headers(), timeout=30)
        if response.status_code not in (200, 404):
            response.raise_for_status()
        self._invalidate_collection(collection)

    def _run_query(
        self,
        collection: str,
        *,
        equals: dict[str, Any] | None = None,
        order_by: str | None = None,
        desc: bool = False,
        limit: int | None = None,
    ) -> list[FirestoreObject]:
        structured: dict[str, Any] = {"from": [{"collectionId": collection}]}
        if equals:
            filters = [
                {
                    "fieldFilter": {
                        "field": {"fieldPath": field},
                        "op": "EQUAL",
                        "value": self._encode_value(value),
                    }
                }
                for field, value in equals.items()
            ]
            structured["where"] = (
                filters[0]
                if len(filters) == 1
                else {"compositeFilter": {"op": "AND", "filters": filters}}
            )
        if order_by:
            structured["orderBy"] = [{
                "field": {"fieldPath": order_by},
                "direction": "DESCENDING" if desc else "ASCENDING",
            }]
        if limit is not None:
            structured["limit"] = limit

        url = f"{self.base_url}:runQuery"
        docs: list[FirestoreObject] = []
        page_token: str | None = None
        while True:
            body: dict[str, Any] = {"structuredQuery": structured}
            if page_token:
                body["pageToken"] = page_token
            response = self._request("POST", url, json=body)
            for row in response.json():
                raw = row.get("document")
                if raw:
                    docs.append(self._decode_doc(collection, raw))
            page_token = response.headers.get("X-Next-Page-Token") or None
            if not page_token:
                break
        return docs

    def list(self, collection: str, order_by: str | None = None, desc: bool = False) -> list[FirestoreObject]:
        cache_key = (collection, "list", order_by, desc)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        docs: list[FirestoreObject] = []
        params: dict[str, str] = {}
        if order_by:
            params["orderBy"] = f"{order_by} desc" if desc else order_by
        url = self._col_url(collection)
        while url:
            response = self._request("GET", url, params=params)
            payload = response.json()
            docs.extend(self._decode_doc(collection, d) for d in payload.get("documents", []))
            next_token = payload.get("nextPageToken")
            if next_token:
                params = {"pageToken": next_token}
                if order_by:
                    params["orderBy"] = f"{order_by} desc" if desc else order_by
            else:
                break
        self._cache_set(cache_key, docs)
        return docs

    def where(self, collection: str, **equals: Any) -> list[FirestoreObject]:
        if not equals:
            return self.list(collection)
        cache_key = (collection, "where", tuple(sorted(equals.items())))
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        docs = self._run_query(collection, equals=equals)
        self._cache_set(cache_key, docs)
        return docs

    def first(self, collection: str, **equals: Any) -> FirestoreObject | None:
        if not equals:
            rows = self.list(collection)
            return rows[0] if rows else None
        cache_key = (collection, "first", tuple(sorted(equals.items())))
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        rows = self._run_query(collection, equals=equals, limit=1)
        doc = rows[0] if rows else None
        self._cache_set(cache_key, doc)
        return doc

    def save(self, obj: FirestoreObject) -> FirestoreObject:
        collection = getattr(obj, "_collection")
        saved = self.set(collection, getattr(obj, "id"), to_plain(obj))
        return saved

    def purge_all(self) -> None:
        for collection in COLLECTIONS | {"_counters"}:
            for doc in self.list(collection):
                self.delete(collection, getattr(doc, "id"))


store = FirestoreStore()
