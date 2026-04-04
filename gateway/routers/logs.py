from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.db.session import get_db
from gateway.dependencies import get_current_user
from gateway.models.admin_user import AdminUser
from gateway.models.request_log import RequestLog
# log_prompt_content is no longer a static setting — it is read from the DB
# via a 10-second in-process TTL cache so the superadmin can toggle it live.
from gateway.models.system_config import get_log_prompt_content

router = APIRouter(dependencies=[Depends(get_current_user)])


def _log_to_dict(log: RequestLog, log_prompt_content: bool = False) -> dict:
    """Serialise a RequestLog row to a response dict.

    log_prompt_content must be True AND the caller must be a superadmin for
    prompt/response content to appear. The calling endpoint resolves both
    conditions and passes the combined result here, so this function stays
    a simple dict builder with no auth knowledge.
    """
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
        "cost_usd": float(log.cost_usd),
        "latency_ms": log.latency_ms,
        "cache_hit": log.cache_hit,
        "guardrail_triggered": log.guardrail_triggered,
        "error_message": log.error_message,
        "started_at": log.started_at.isoformat() if log.started_at else None,
        "created_at": log.created_at.isoformat() if log.created_at else None,
    }
    # Prompt and response content are only included when content logging is enabled.
    # The flag is controlled at runtime by a superadmin via PATCH /users/runtime-settings.
    if log_prompt_content:
        d["prompt_messages"] = log.prompt_messages
        d["response_content"] = log.response_content
    return d


@router.get("")
async def list_logs(
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
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
) -> dict:
    q = select(RequestLog)
    if status_code:
        q = q.where(RequestLog.status_code == status_code)
    if model:
        q = q.where(RequestLog.litellm_model_name.ilike(f"%{model}%"))
    if team_id:
        q = q.where(RequestLog.team_id == team_id)
    if key_id:
        q = q.where(RequestLog.virtual_key_id == key_id)
    if cache_hit is not None:
        q = q.where(RequestLog.cache_hit == cache_hit)
    if from_dt:
        q = q.where(RequestLog.started_at >= from_dt)
    if to_dt:
        q = q.where(RequestLog.started_at <= to_dt)
    if search:
        q = q.where(RequestLog.request_id.ilike(f"%{search}%"))

    count_q = select(func.count()).select_from(q.subquery())
    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    q = q.order_by(RequestLog.started_at.desc()).offset((page - 1) * limit).limit(limit)
    result = await db.execute(q)
    logs = result.scalars().all()

    # Prompt content is only exposed when the runtime flag is on AND the caller
    # is a superadmin. Regular admins see metadata only, regardless of the flag.
    log_content = current_user.is_superadmin and await get_log_prompt_content(db)

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "items": [_log_to_dict(log, log_content) for log in logs],
    }


@router.get("/stats")
async def log_stats(
    hours: int = Query(24, ge=1, le=720),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from_dt = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = await db.execute(
        select(
            func.count(RequestLog.id).label("total"),
            func.sum((RequestLog.status_code == 200).cast(func.Integer if False else type(1))).label("success"),
            func.coalesce(func.avg(RequestLog.latency_ms), 0).label("avg_latency"),
            func.coalesce(func.sum(RequestLog.cost_usd), 0).label("total_cost"),
            func.coalesce(func.sum(RequestLog.total_tokens), 0).label("total_tokens"),
        ).where(RequestLog.started_at >= from_dt)
    )
    row = result.one()
    total = int(row.total or 0)
    return {
        "total_requests": total,
        "avg_latency_ms": round(float(row.avg_latency or 0)),
        "total_cost_usd": float(row.total_cost or 0),
        "total_tokens": int(row.total_tokens or 0),
    }


@router.get("/{log_id}")
async def get_log(
    log_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
) -> dict:
    log = await db.get(RequestLog, log_id)
    if not log:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Log not found")
    # Same dual condition: flag on AND caller is superadmin.
    log_content = current_user.is_superadmin and await get_log_prompt_content(db)
    return _log_to_dict(log, log_content)
