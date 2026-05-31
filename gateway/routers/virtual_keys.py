from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status

from gateway.db.session import get_db
from gateway.dependencies import get_current_user
from gateway.firestore_store import FirestoreObject, FirestoreStore
from gateway.schemas.virtual_key import (
    VirtualKeyCreate,
    VirtualKeyCreateResponse,
    VirtualKeyResponse,
    VirtualKeyUpdate,
)
from gateway.services.key_service import generate_virtual_key

router = APIRouter(dependencies=[Depends(get_current_user)])


def _next_monthly_reset() -> datetime:
    now = datetime.now(timezone.utc)
    if now.month == 12:
        return datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    return datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)


def _enrich(key: FirestoreObject, db: FirestoreStore, teams: dict[int, str] | None = None) -> dict:
    data = {k: v for k, v in vars(key).items() if not k.startswith("_")}
    team_id = getattr(key, "team_id", None)
    if team_id and teams is not None:
        data["team_name"] = teams.get(team_id)
    elif team_id:
        team = db.get("teams", team_id)
        data["team_name"] = team.name if team else None
    else:
        data["team_name"] = None
    return data


def _assert_owns_key(key: FirestoreObject, current_user: FirestoreObject) -> None:
    if not current_user.is_superadmin and key.created_by_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: not your key")


@router.get("", response_model=list[VirtualKeyResponse])
def list_keys(
    team_id: int | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: FirestoreStore = Depends(get_db),
    current_user: FirestoreObject = Depends(get_current_user),
):
    keys = db.list("virtual_keys", order_by="created_at", desc=True)
    if not current_user.is_superadmin:
        keys = [k for k in keys if k.created_by_user_id == current_user.id]
    if team_id:
        keys = [k for k in keys if k.team_id == team_id]
    if search:
        keys = [k for k in keys if search.lower() in k.owner_label.lower()]
    keys = keys[(page - 1) * limit:page * limit]
    teams = {t.id: t.name for t in db.list("teams")}
    return [_enrich(k, db, teams) for k in keys]


@router.post("", response_model=VirtualKeyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_key(
    body: VirtualKeyCreate,
    db: FirestoreStore = Depends(get_db),
    current_user: FirestoreObject = Depends(get_current_user),
):
    full_key, key_hash, key_prefix = generate_virtual_key()
    key = db.create("virtual_keys", {
        **body.model_dump(),
        "key_hash": key_hash,
        "key_prefix": key_prefix,
        "budget_reset_at": _next_monthly_reset(),
        "current_spend_usd": 0,
        "created_by_user_id": current_user.id,
        "is_active": True,
    })
    data = _enrich(key, db)
    data["full_key"] = full_key
    return data


@router.get("/{key_id}", response_model=VirtualKeyResponse)
async def get_key(
    key_id: int,
    db: FirestoreStore = Depends(get_db),
    current_user: FirestoreObject = Depends(get_current_user),
):
    key = db.get("virtual_keys", key_id)
    if not key:
        raise HTTPException(status_code=404, detail="Key not found")
    _assert_owns_key(key, current_user)
    return _enrich(key, db)


@router.patch("/{key_id}", response_model=VirtualKeyResponse)
async def update_key(
    key_id: int,
    body: VirtualKeyUpdate,
    db: FirestoreStore = Depends(get_db),
    current_user: FirestoreObject = Depends(get_current_user),
):
    key = db.get("virtual_keys", key_id)
    if not key:
        raise HTTPException(status_code=404, detail="Key not found")
    _assert_owns_key(key, current_user)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(key, field, value)
    db.save(key)
    return _enrich(key, db)


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_key(
    key_id: int,
    db: FirestoreStore = Depends(get_db),
    current_user: FirestoreObject = Depends(get_current_user),
):
    key = db.get("virtual_keys", key_id)
    if not key:
        raise HTTPException(status_code=404, detail="Key not found")
    _assert_owns_key(key, current_user)
    db.delete("virtual_keys", key_id)


@router.post("/{key_id}/rotate", response_model=VirtualKeyCreateResponse)
async def rotate_key(
    key_id: int,
    db: FirestoreStore = Depends(get_db),
    current_user: FirestoreObject = Depends(get_current_user),
):
    key = db.get("virtual_keys", key_id)
    if not key:
        raise HTTPException(status_code=404, detail="Key not found")
    _assert_owns_key(key, current_user)
    full_key, key_hash, key_prefix = generate_virtual_key()
    key.key_hash = key_hash
    key.key_prefix = key_prefix
    db.save(key)
    data = _enrich(key, db)
    data["full_key"] = full_key
    return data
