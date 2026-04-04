from datetime import datetime
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.db.session import get_db
from gateway.dependencies import get_current_user, require_superadmin
from gateway.models.alert_rule import AlertEvent, AlertRule

router = APIRouter(dependencies=[Depends(get_current_user)])


class AlertRuleCreate(BaseModel):
    name: str
    metric: str  # spend_pct|error_rate|latency_p99|budget_remaining_usd
    threshold_value: Decimal
    scope_type: str = "global"
    scope_id: int | None = None
    notification_channel: str = "log"  # log|email|webhook
    notification_target: str | None = None


class AlertRuleUpdate(BaseModel):
    name: str | None = None
    threshold_value: Decimal | None = None
    notification_channel: str | None = None
    notification_target: str | None = None
    is_active: bool | None = None


class AlertRuleResponse(BaseModel):
    id: int
    name: str
    metric: str
    threshold_value: Decimal
    scope_type: str
    scope_id: int | None
    notification_channel: str
    notification_target: str | None
    is_active: bool
    last_triggered_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertEventResponse(BaseModel):
    id: int
    rule_id: int
    rule_name: str
    metric: str
    actual_value: Decimal
    threshold_value: Decimal
    message: str
    fired_at: datetime

    model_config = {"from_attributes": True}


# ── Rules ─────────────────────────────────────────────────────────────────────

@router.get("/rules", response_model=list[AlertRuleResponse])
async def list_rules(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AlertRule).order_by(AlertRule.created_at.desc()))
    return result.scalars().all()


@router.post("/rules", response_model=AlertRuleResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_superadmin)])
async def create_rule(body: AlertRuleCreate, db: AsyncSession = Depends(get_db)):
    rule = AlertRule(**body.model_dump())
    db.add(rule)
    await db.flush()
    await db.refresh(rule)
    return rule


@router.patch("/rules/{rule_id}", response_model=AlertRuleResponse,
              dependencies=[Depends(require_superadmin)])
async def update_rule(rule_id: int, body: AlertRuleUpdate, db: AsyncSession = Depends(get_db)):
    rule = await db.get(AlertRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    await db.flush()
    return rule


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_superadmin)])
async def delete_rule(rule_id: int, db: AsyncSession = Depends(get_db)):
    rule = await db.get(AlertRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    await db.delete(rule)


# ── History ───────────────────────────────────────────────────────────────────

@router.get("/history", response_model=list[AlertEventResponse])
async def alert_history(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(AlertEvent)
        .order_by(AlertEvent.fired_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    result = await db.execute(q)
    return result.scalars().all()
