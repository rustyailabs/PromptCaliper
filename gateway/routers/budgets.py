from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status

from gateway.db.session import get_db
from gateway.dependencies import get_current_user, require_superadmin
from gateway.firestore_store import FirestoreStore
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
def list_policies(db: FirestoreStore = Depends(get_db)):
    return db.list("budget_policies", order_by="created_at", desc=True)


@router.post("", response_model=BudgetPolicyResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_superadmin)])
async def create_policy(body: BudgetPolicyCreate, db: FirestoreStore = Depends(get_db)):
    return db.create("budget_policies", {**body.model_dump(), "is_active": True})


@router.patch("/{policy_id}", response_model=BudgetPolicyResponse,
              dependencies=[Depends(require_superadmin)])
async def update_policy(policy_id: int, body: BudgetPolicyUpdate, db: FirestoreStore = Depends(get_db)):
    policy = db.get("budget_policies", policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(policy, field, value)
    return db.save(policy)


@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_superadmin)])
async def delete_policy(policy_id: int, db: FirestoreStore = Depends(get_db)):
    if not db.get("budget_policies", policy_id):
        raise HTTPException(status_code=404, detail="Policy not found")
    db.delete("budget_policies", policy_id)


@router.get("/summary")
def org_summary(period: str | None = Query(None), db: FirestoreStore = Depends(get_db)):
    return get_org_spend(db, period)


@router.get("/spend/by-team")
def spend_by_team(period: str | None = Query(None), db: FirestoreStore = Depends(get_db)):
    return get_spend_by_team(db, period)


@router.get("/spend/by-model")
def spend_by_model(period: str | None = Query(None), db: FirestoreStore = Depends(get_db)):
    return get_spend_by_model(db, period)


@router.get("/spend/by-key")
def spend_by_key(period: str | None = Query(None), db: FirestoreStore = Depends(get_db)):
    return get_spend_by_key(db, period)


@router.get("/spend/timeseries")
def spend_timeseries(
    granularity: str = Query("day"),
    days: int = Query(7, ge=1, le=90),
    db: FirestoreStore = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    return get_timeseries(db, now - timedelta(days=days), now, granularity)
