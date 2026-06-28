from datetime import datetime, timezone, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query

from gateway.db.session import get_db
from gateway.dependencies import get_current_user
from gateway.firestore_store import FirestoreStore
from gateway.services.spend_service import get_timeseries

router = APIRouter(dependencies=[Depends(get_current_user)])

TimeRange = Literal["1h", "24h", "7d", "30d"]
_DELTA_MAP = {"1h": timedelta(hours=1), "24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30)}


def _time_range(time_range: TimeRange) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    return now - _DELTA_MAP[time_range], now


def _logs(db: FirestoreStore, from_dt: datetime, to_dt: datetime):
    return [l for l in db.list("request_logs") if from_dt <= l.started_at <= to_dt]


@router.get("/overview")
def overview(time_range: TimeRange = Query("24h"), db: FirestoreStore = Depends(get_db)) -> dict:
    from_dt, to_dt = _time_range(time_range)
    logs = _logs(db, from_dt, to_dt)
    total = len(logs)
    cache_hits = len([l for l in logs if l.cache_hit])
    return {
        "total_requests": total,
        "avg_latency_ms": round(sum(float(l.latency_ms or 0) for l in logs) / total) if total else 0,
        "total_cost_usd": sum(float(l.cost_usd or 0) for l in logs),
        "total_tokens": sum(int(l.total_tokens or 0) for l in logs),
        "prompt_tokens": sum(int(l.prompt_tokens or 0) for l in logs),
        "completion_tokens": sum(int(l.completion_tokens or 0) for l in logs),
        "error_count": len([l for l in logs if l.status_code >= 400]),
        "blocked_count": len([l for l in logs if l.status_code == 429]),
        "cache_hits": cache_hits,
        "cache_hit_rate": round(cache_hits / total * 100, 1) if total else 0,
    }


@router.get("/timeseries")
def timeseries(time_range: TimeRange = Query("24h"), granularity: str = Query("hour"), db: FirestoreStore = Depends(get_db)) -> list:
    from_dt, to_dt = _time_range(time_range)
    return get_timeseries(db, from_dt, to_dt, granularity)


@router.get("/model-distribution")
def model_distribution(time_range: TimeRange = Query("24h"), db: FirestoreStore = Depends(get_db)) -> list:
    from_dt, to_dt = _time_range(time_range)
    logs = _logs(db, from_dt, to_dt)
    grouped: dict[str, dict] = {}
    for log in logs:
        item = grouped.setdefault(log.litellm_model_name, {"model": log.litellm_model_name, "request_count": 0, "cost_usd": 0.0})
        item["request_count"] += 1
        item["cost_usd"] += float(log.cost_usd or 0)
    total = sum(v["request_count"] for v in grouped.values())
    return [{**v, "pct": round(v["request_count"] / total * 100, 1) if total else 0} for v in grouped.values()]


@router.get("/team-spend")
def team_spend_history(months: int = Query(6, ge=1, le=24), db: FirestoreStore = Depends(get_db)) -> list:
    now = datetime.now(timezone.utc).replace(day=1)
    periods = []
    cursor = now
    for _ in range(months):
        periods.append(cursor.strftime("%Y-%m"))
        cursor = (cursor - timedelta(days=1)).replace(day=1)
    periods.reverse()
    pivot = {p: {"month": p} for p in periods}
    teams = {t.id: t.name for t in db.list("teams")}
    for row in db.list("spend_ledger"):
        if row.period_month not in pivot:
            continue
        pivot[row.period_month][teams.get(row.team_id, "Unassigned")] = pivot[row.period_month].get(teams.get(row.team_id, "Unassigned"), 0) + float(row.amount_usd or 0)
    return list(pivot.values())


@router.get("/token-economics")
def token_economics(days: int = Query(7, ge=1, le=30), db: FirestoreStore = Depends(get_db)) -> list:
    from_dt = datetime.now(timezone.utc) - timedelta(days=days)
    grouped: dict[str, dict] = {}
    for log in db.list("request_logs"):
        if log.started_at < from_dt:
            continue
        day = log.started_at.strftime("%Y-%m-%d")
        item = grouped.setdefault(day, {"day": day, "input_tokens": 0, "output_tokens": 0})
        item["input_tokens"] += int(log.prompt_tokens or 0)
        item["output_tokens"] += int(log.completion_tokens or 0)
    return [grouped[k] for k in sorted(grouped)]


@router.get("/breakdown")
def breakdown(
    by: Literal["session_id", "client_service_tag", "virtual_key_id"] = Query("client_service_tag"),
    time_range: TimeRange = Query("24h"),
    virtual_key_id: int | None = Query(None, description="Filter logs to a specific virtual key"),
    session_id: str | None = Query(None, description="Filter logs to a specific session"),
    client_service_tag: str | None = Query(None, description="Filter logs to a specific client service tag"),
    db: FirestoreStore = Depends(get_db),
) -> list:
    from_dt, to_dt = _time_range(time_range)
    logs = _logs(db, from_dt, to_dt)

    # Apply filters
    if virtual_key_id is not None:
        logs = [l for l in logs if l.virtual_key_id == virtual_key_id]
    if session_id is not None:
        logs = [l for l in logs if getattr(l, "session_id", None) == session_id]
    if client_service_tag is not None:
        logs = [l for l in logs if getattr(l, "client_service_tag", None) == client_service_tag]

    # Build a lookup for virtual key labels when grouping by virtual_key_id
    key_labels: dict[int, str] = {}
    if by == "virtual_key_id":
        for vk in db.list("virtual_keys"):
            prefix = getattr(vk, "key_prefix", "sk-???")
            label = getattr(vk, "owner_label", "")
            key_labels[vk.id] = f"{prefix} ({label})" if label else prefix

    grouped: dict[str, dict] = {}
    for log in logs:
        val = getattr(log, by, None)
        if by == "virtual_key_id" and val is not None:
            key_str = key_labels.get(val, f"Key #{val}")
            raw_id = val
        else:
            key_str = str(val) if val not in (None, "") else "Unspecified"
            raw_id = None

        item = grouped.setdefault(key_str, {
            "key": key_str,
            "raw_id": raw_id,
            "request_count": 0,
            "cost_usd": 0.0,
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "avg_latency_ms": 0.0,
            "_latency_sum": 0.0,
        })
        item["request_count"] += 1
        item["cost_usd"] += float(log.cost_usd or 0)
        item["total_tokens"] += int(log.total_tokens or 0)
        item["prompt_tokens"] += int(log.prompt_tokens or 0)
        item["completion_tokens"] += int(log.completion_tokens or 0)
        item["_latency_sum"] += float(log.latency_ms or 0)

    total_requests = sum(v["request_count"] for v in grouped.values())
    total_cost = sum(v["cost_usd"] for v in grouped.values())

    result = []
    for k, v in grouped.items():
        avg_lat = round(v["_latency_sum"] / v["request_count"]) if v["request_count"] else 0
        result.append({
            "key": v["key"],
            "raw_id": v["raw_id"],
            "request_count": v["request_count"],
            "cost_usd": v["cost_usd"],
            "total_tokens": v["total_tokens"],
            "prompt_tokens": v["prompt_tokens"],
            "completion_tokens": v["completion_tokens"],
            "avg_latency_ms": avg_lat,
            "pct_requests": round(v["request_count"] / total_requests * 100, 1) if total_requests else 0,
            "pct_cost": round(v["cost_usd"] / total_cost * 100, 1) if total_cost else 0,
        })

    result.sort(key=lambda x: (x["cost_usd"], x["request_count"]), reverse=True)
    return result

