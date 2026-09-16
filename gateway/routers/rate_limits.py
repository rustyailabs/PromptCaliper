from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from gateway.db.session import get_db
from gateway.dependencies import get_current_user, require_superadmin
from gateway.firestore_store import FirestoreStore
from gateway.schemas.rate_limit import RateLimitPolicyCreate, RateLimitPolicyResponse, RateLimitPolicyUpdate

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[RateLimitPolicyResponse])
def list_policies(db: FirestoreStore = Depends(get_db)):
    return db.list("rate_limit_policies", order_by="created_at", desc=True)


@router.post("", response_model=RateLimitPolicyResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_superadmin)])
async def create_policy(body: RateLimitPolicyCreate, db: FirestoreStore = Depends(get_db)):
    return db.create("rate_limit_policies", {**body.model_dump(), "is_active": True})


@router.patch("/{policy_id}", response_model=RateLimitPolicyResponse,
              dependencies=[Depends(require_superadmin)])
async def update_policy(policy_id: int, body: RateLimitPolicyUpdate, db: FirestoreStore = Depends(get_db)):
    policy = db.get("rate_limit_policies", policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(policy, field, value)
    return db.save(policy)


@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_superadmin)])
async def delete_policy(policy_id: int, db: FirestoreStore = Depends(get_db)):
    if not db.get("rate_limit_policies", policy_id):
        raise HTTPException(status_code=404, detail="Policy not found")
    db.delete("rate_limit_policies", policy_id)


@router.get("/current-usage")
def current_usage(db: FirestoreStore = Depends(get_db)):
    keys = [
        k for k in db.where("virtual_keys", is_active=True)
        if getattr(k, "rpm_limit", None) is not None or getattr(k, "tpm_limit", None) is not None
    ]
    minute_start = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    logs = [l for l in db.list("request_logs") if l.started_at >= minute_start]
    out = []
    for key in keys:
        key_logs = [l for l in logs if l.virtual_key_id == key.id]
        out.append({
            "key_id": key.id,
            "key_prefix": key.key_prefix,
            "rpm_limit": key.rpm_limit,
            "tpm_limit": key.tpm_limit,
            "rpm": len(key_logs),
            "tpm": sum(int(l.total_tokens or 0) for l in key_logs),
        })
    return out
