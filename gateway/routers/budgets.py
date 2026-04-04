from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.db.session import get_db
from gateway.dependencies import get_current_user, require_superadmin
from gateway.models.budget_policy import BudgetPolicy
from gateway.schemas.budget import BudgetPolicyCreate, BudgetPolicyResponse, BudgetPolicyUpdate
from gateway.services.spend_service import (
    get_org_spend,
    get_spend_by_key,
    get_spend_by_model,
    get_spend_by_team,
    get_timeseries,
)

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[BudgetPolicyResponse])
async def list_policies(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(BudgetPolicy).order_by(BudgetPolicy.created_at.desc()))
    return result.scalars().all()


@router.post("", response_model=BudgetPolicyResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_superadmin)])
async def create_policy(body: BudgetPolicyCreate, db: AsyncSession = Depends(get_db)):
    policy = BudgetPolicy(**body.model_dump())
    db.add(policy)
    await db.flush()
    await db.refresh(policy)
    return policy


@router.patch("/{policy_id}", response_model=BudgetPolicyResponse,
              dependencies=[Depends(require_superadmin)])
async def update_policy(policy_id: int, body: BudgetPolicyUpdate, db: AsyncSession = Depends(get_db)):
    policy = await db.get(BudgetPolicy, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(policy, field, value)
    await db.flush()
    return policy


@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_superadmin)])
async def delete_policy(policy_id: int, db: AsyncSession = Depends(get_db)):
    policy = await db.get(BudgetPolicy, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    await db.delete(policy)


@router.get("/summary")
async def org_summary(period: str | None = Query(None), db: AsyncSession = Depends(get_db)):
    return await get_org_spend(db, period)


@router.get("/spend/by-team")
async def spend_by_team(period: str | None = Query(None), db: AsyncSession = Depends(get_db)):
    return await get_spend_by_team(db, period)


@router.get("/spend/by-model")
async def spend_by_model(period: str | None = Query(None), db: AsyncSession = Depends(get_db)):
    return await get_spend_by_model(db, period)


@router.get("/spend/by-key")
async def spend_by_key(period: str | None = Query(None), db: AsyncSession = Depends(get_db)):
    return await get_spend_by_key(db, period)


@router.get("/spend/timeseries")
async def spend_timeseries(
    granularity: str = Query("day"),
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    from_dt = now - timedelta(days=days)
    return await get_timeseries(db, from_dt, now, granularity)
