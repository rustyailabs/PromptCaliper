from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query

from gateway.db.session import get_db
from gateway.dependencies import get_current_user
from gateway.firestore_store import FirestoreObject, FirestoreStore
from gateway.models.system_config import get_log_prompt_content

router = APIRouter(dependencies=[Depends(get_current_user)])


def _log_to_dict(log: FirestoreObject, log_prompt_content: bool = False) -> dict:
    d = {
        "id": log.id,
        "request_id": log.request_id,
        "virtual_key_id": log.virtual_key_id,
        "team_id": log.team_id,
        "model": log.litellm_model_name,
        "requested_model": log.requested_model,
        "status_code": log.status_code,
        "prompt_tokens": log.prompt_tokens,
        "completion_tokens": log.completion_tokens,
        "total_tokens": log.total_tokens,
        "cost_usd": float(log.cost_usd or 0),
        "latency_ms": log.latency_ms,
        "cache_hit": log.cache_hit,
        "guardrail_triggered": log.guardrail_triggered,
        "error_message": log.error_message,
        "started_at": log.started_at.isoformat() if log.started_at else None,
        "created_at": log.created_at.isoformat() if log.created_at else None,
    }
    if log_prompt_content:
        d["prompt_messages"] = log.prompt_messages
        d["response_content"] = log.response_content
    return d


@router.get("")
def list_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    status_code: int | None = Query(None),
    model: str | None = Query(None),
    team_id: int | None = Query(None),
    key_id: int | None = Query(None),
    cache_hit: bool | None = Query(None),
    from_dt: datetime | None = Query(None, alias="from"),
    to_dt: datetime | None = Query(None, alias="to"),
    search: str | None = Query(None),
    db: FirestoreStore = Depends(get_db),
    current_user: FirestoreObject = Depends(get_current_user),
) -> dict:
    logs = db.list("request_logs", order_by="started_at", desc=True)
    if status_code:
        logs = [l for l in logs if l.status_code == status_code]
    if model:
        logs = [l for l in logs if model.lower() in (l.litellm_model_name or "").lower()]
    if team_id:
        logs = [l for l in logs if l.team_id == team_id]
    if key_id:
        logs = [l for l in logs if l.virtual_key_id == key_id]
    if cache_hit is not None:
        logs = [l for l in logs if l.cache_hit == cache_hit]
    if from_dt:
        logs = [l for l in logs if l.started_at >= from_dt]
    if to_dt:
        logs = [l for l in logs if l.started_at <= to_dt]
    if search:
        logs = [l for l in logs if search.lower() in l.request_id.lower()]
    total = len(logs)
    logs = logs[(page - 1) * limit:page * limit]
    log_content = current_user.is_superadmin and get_log_prompt_content(db)
    return {"total": total, "page": page, "limit": limit, "items": [_log_to_dict(log, log_content) for log in logs]}


@router.get("/stats")
def log_stats(hours: int = Query(24, ge=1, le=720), db: FirestoreStore = Depends(get_db)) -> dict:
    from_dt = datetime.now(timezone.utc) - timedelta(hours=hours)
    logs = [l for l in db.list("request_logs") if l.started_at >= from_dt]
    return {
        "total_requests": len(logs),
        "avg_latency_ms": round(sum(float(l.latency_ms or 0) for l in logs) / len(logs)) if logs else 0,
        "total_cost_usd": sum(float(l.cost_usd or 0) for l in logs),
        "total_tokens": sum(int(l.total_tokens or 0) for l in logs),
    }


@router.get("/{log_id}")
def get_log(
    log_id: int,
    db: FirestoreStore = Depends(get_db),
    current_user: FirestoreObject = Depends(get_current_user),
) -> dict:
    log = db.get("request_logs", log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    log_content = current_user.is_superadmin and get_log_prompt_content(db)
    return _log_to_dict(log, log_content)
