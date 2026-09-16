from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from gateway.db.session import get_db
from gateway.dependencies import get_current_user, require_superadmin
from gateway.firestore_store import FirestoreStore

router = APIRouter(dependencies=[Depends(get_current_user)])


class AlertRuleCreate(BaseModel):
    name: str
    metric: str
    threshold_value: Decimal
    scope_type: str = "global"
    scope_id: int | None = None
    notification_channel: str = "log"
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
    rule_id: int | None
    rule_name: str
    metric: str
    actual_value: Decimal
    threshold_value: Decimal
    message: str
    fired_at: datetime

    model_config = {"from_attributes": True}


@router.get("/rules", response_model=list[AlertRuleResponse])
def list_rules(db: FirestoreStore = Depends(get_db)):
    return db.list("alert_rules", order_by="created_at", desc=True)


@router.post("/rules", response_model=AlertRuleResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_superadmin)])
async def create_rule(body: AlertRuleCreate, db: FirestoreStore = Depends(get_db)):
    return db.create("alert_rules", {**body.model_dump(), "is_active": True, "last_triggered_at": None})


@router.patch("/rules/{rule_id}", response_model=AlertRuleResponse,
              dependencies=[Depends(require_superadmin)])
async def update_rule(rule_id: int, body: AlertRuleUpdate, db: FirestoreStore = Depends(get_db)):
    rule = db.get("alert_rules", rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    return db.save(rule)


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_superadmin)])
async def delete_rule(rule_id: int, db: FirestoreStore = Depends(get_db)):
    if not db.get("alert_rules", rule_id):
        raise HTTPException(status_code=404, detail="Rule not found")
    db.delete("alert_rules", rule_id)


@router.get("/history", response_model=list[AlertEventResponse])
def alert_history(page: int = Query(1, ge=1), limit: int = Query(50, ge=1, le=200), db: FirestoreStore = Depends(get_db)):
    events = db.list("alert_events", order_by="fired_at", desc=True)
    return events[(page - 1) * limit:page * limit]
