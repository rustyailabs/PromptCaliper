from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.db.session import get_db
from gateway.dependencies import get_current_user, require_superadmin
from gateway.models.rate_limit_policy import RateLimitPolicy
from gateway.models.request_log import RequestLog
from gateway.schemas.rate_limit import RateLimitPolicyCreate, RateLimitPolicyResponse, RateLimitPolicyUpdate

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[RateLimitPolicyResponse])
async def list_policies(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RateLimitPolicy).order_by(RateLimitPolicy.created_at.desc()))
    return result.scalars().all()


@router.post("", response_model=RateLimitPolicyResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_superadmin)])
async def create_policy(body: RateLimitPolicyCreate, db: AsyncSession = Depends(get_db)):
    policy = RateLimitPolicy(**body.model_dump())
    db.add(policy)
    await db.flush()
    await db.refresh(policy)
    return policy


@router.patch("/{policy_id}", response_model=RateLimitPolicyResponse,
              dependencies=[Depends(require_superadmin)])
async def update_policy(policy_id: int, body: RateLimitPolicyUpdate, db: AsyncSession = Depends(get_db)):
    policy = await db.get(RateLimitPolicy, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(policy, field, value)
    await db.flush()
    return policy


@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_superadmin)])
async def delete_policy(policy_id: int, db: AsyncSession = Depends(get_db)):
    policy = await db.get(RateLimitPolicy, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    await db.delete(policy)


@router.get("/current-usage")
async def current_usage(db: AsyncSession = Depends(get_db)):
    """Returns current RPM/TPM usage for this minute, read from request_logs (DB-backed, survives restarts)."""
    from gateway.models.virtual_key import VirtualKey

    # Keys that have at least one limit configured
    result = await db.execute(
        select(VirtualKey).where(
            VirtualKey.is_active == True,
            or_(VirtualKey.rpm_limit.isnot(None), VirtualKey.tpm_limit.isnot(None)),
        )
    )
    keys = result.scalars().all()
    if not keys:
        return []

    # Current UTC minute window — pass datetime objects, not strings, so the
    # comparison is type-safe on both SQLite and PostgreSQL.
    now = datetime.now(timezone.utc)
    minute_start = now.replace(second=0, microsecond=0)

    key_ids = [k.id for k in keys]

    # Single query: count requests + sum tokens per key for this minute
    usage_result = await db.execute(
        select(
            RequestLog.virtual_key_id,
            func.count(RequestLog.id).label("rpm"),
            func.coalesce(func.sum(RequestLog.total_tokens), 0).label("tpm"),
        )
        .where(
            RequestLog.virtual_key_id.in_(key_ids),
            RequestLog.started_at >= minute_start,
        )
        .group_by(RequestLog.virtual_key_id)
    )
    usage_by_key = {row.virtual_key_id: {"rpm": row.rpm, "tpm": int(row.tpm)} for row in usage_result.all()}

    return [
        {
            "key_id": k.id,
            "key_prefix": k.key_prefix,
            "rpm_limit": k.rpm_limit,
            "tpm_limit": k.tpm_limit,
            "rpm": usage_by_key.get(k.id, {}).get("rpm", 0),
            "tpm": usage_by_key.get(k.id, {}).get("tpm", 0),
        }
        for k in keys
    ]
