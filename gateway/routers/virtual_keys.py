from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.db.session import get_db
from gateway.dependencies import get_current_user
from gateway.models.admin_user import AdminUser
from gateway.models.virtual_key import VirtualKey
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


def _enrich(key: VirtualKey) -> dict:
    data = {c.key: getattr(key, c.key) for c in key.__table__.columns}
    data["team_name"] = key.team.name if key.team else None
    return data


def _assert_owns_key(key: VirtualKey, current_user: AdminUser) -> None:
    """Raise 403 if a non-superadmin tries to act on a key they didn't create."""
    if not current_user.is_superadmin and key.created_by_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: not your key")


@router.get("", response_model=list[VirtualKeyResponse])
async def list_keys(
    team_id: int | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    q = select(VirtualKey)
    # Regular admins only see keys they created; superadmins see all
    if not current_user.is_superadmin:
        q = q.where(VirtualKey.created_by_user_id == current_user.id)
    if team_id:
        q = q.where(VirtualKey.team_id == team_id)
    if search:
        q = q.where(VirtualKey.owner_label.ilike(f"%{search}%"))
    q = q.offset((page - 1) * limit).limit(limit).order_by(VirtualKey.created_at.desc())
    result = await db.execute(q)
    keys = result.scalars().all()
    return [_enrich(k) for k in keys]


@router.post("", response_model=VirtualKeyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_key(
    body: VirtualKeyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    full_key, key_hash, key_prefix = generate_virtual_key()
    key = VirtualKey(
        key_hash=key_hash,
        key_prefix=key_prefix,
        owner_label=body.owner_label,
        team_id=body.team_id,
        monthly_budget_usd=body.monthly_budget_usd,
        budget_action=body.budget_action,
        rpm_limit=body.rpm_limit,
        tpm_limit=body.tpm_limit,
        allowed_models=body.allowed_models,
        expires_at=body.expires_at,
        budget_reset_at=_next_monthly_reset(),
        current_spend_usd=0,
        created_by_user_id=current_user.id,
    )
    db.add(key)
    await db.flush()
    await db.refresh(key)
    data = _enrich(key)
    data["full_key"] = full_key  # One-time reveal
    return data


@router.get("/{key_id}", response_model=VirtualKeyResponse)
async def get_key(
    key_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    key = await db.get(VirtualKey, key_id)
    if not key:
        raise HTTPException(status_code=404, detail="Key not found")
    _assert_owns_key(key, current_user)
    return _enrich(key)


@router.patch("/{key_id}", response_model=VirtualKeyResponse)
async def update_key(
    key_id: int,
    body: VirtualKeyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    key = await db.get(VirtualKey, key_id)
    if not key:
        raise HTTPException(status_code=404, detail="Key not found")
    _assert_owns_key(key, current_user)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(key, field, value)
    await db.flush()
    return _enrich(key)


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_key(
    key_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    key = await db.get(VirtualKey, key_id)
    if not key:
        raise HTTPException(status_code=404, detail="Key not found")
    _assert_owns_key(key, current_user)
    await db.delete(key)


@router.post("/{key_id}/rotate", response_model=VirtualKeyCreateResponse)
async def rotate_key(
    key_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    key = await db.get(VirtualKey, key_id)
    if not key:
        raise HTTPException(status_code=404, detail="Key not found")
    _assert_owns_key(key, current_user)
    full_key, key_hash, key_prefix = generate_virtual_key()
    key.key_hash = key_hash
    key.key_prefix = key_prefix
    await db.flush()
    data = _enrich(key)
    data["full_key"] = full_key
    return data
