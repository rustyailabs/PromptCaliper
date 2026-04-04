from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.auth.schemas import AdminUserResponse
from gateway.auth.service import hash_password
from gateway.db.session import get_db
from gateway.dependencies import get_current_user, require_superadmin
from gateway.models.admin_user import AdminUser

router = APIRouter(dependencies=[Depends(get_current_user)])


# ---------------------------------------------------------------------------
# Runtime settings — superadmin only
# ---------------------------------------------------------------------------

class RuntimeSettings(BaseModel):
    """Superadmin-controlled flags that can be toggled at runtime via the UI.

    These are persisted in the system_config table (singleton row id=1) so
    they survive process restarts. An in-process TTL cache in system_config.py
    ensures DB reads on the hot LLM-request path are rare (at most once per
    10 s per worker process).
    """
    log_prompt_content: bool


@router.get(
    "/runtime-settings",
    response_model=RuntimeSettings,
    dependencies=[Depends(require_superadmin)],
    summary="Get runtime configuration flags (superadmin only)",
)
async def get_runtime_settings(db: AsyncSession = Depends(get_db)) -> RuntimeSettings:
    """Return the current runtime configuration flags.

    Restricted to superadmins — regular admins have no need to read or change
    system-level privacy/debug settings.
    """
    from gateway.models.system_config import SystemConfig

    config = await db.get(SystemConfig, 1)
    return RuntimeSettings(
        log_prompt_content=config.log_prompt_content if config else False
    )


@router.patch(
    "/runtime-settings",
    response_model=RuntimeSettings,
    dependencies=[Depends(require_superadmin)],
    summary="Update runtime configuration flags (superadmin only)",
)
async def update_runtime_settings(
    body: RuntimeSettings,
    db: AsyncSession = Depends(get_db),
) -> RuntimeSettings:
    """Toggle runtime configuration flags without a server restart.

    After the DB write, the in-process TTL cache for this worker is invalidated
    immediately. Other workers (in multi-worker prod deployments) will pick up
    the change within 10 seconds via their own TTL expiry.

    Security: requires a valid JWT *and* is_superadmin=True on the DB record.
    Regular admins receive HTTP 403.
    """
    from gateway.models.system_config import (
        SystemConfig,
        invalidate_log_prompt_content_cache,
    )

    config = await db.get(SystemConfig, 1)
    if not config:
        # Row missing (should not happen after seed, but handle defensively)
        config = SystemConfig(id=1, log_prompt_content=body.log_prompt_content)
        db.add(config)
    else:
        config.log_prompt_content = body.log_prompt_content

    await db.flush()
    # Invalidate this worker's in-process cache so the change is visible
    # immediately, not after the next TTL expiry.
    invalidate_log_prompt_content_cache()
    return RuntimeSettings(log_prompt_content=config.log_prompt_content)


class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    is_superadmin: bool = False


class UserUpdate(BaseModel):
    email: str | None = None
    password: str | None = None
    is_superadmin: bool | None = None
    is_active: bool | None = None


@router.get("", response_model=list[AdminUserResponse])
async def list_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AdminUser).order_by(AdminUser.username))
    return result.scalars().all()


@router.post("", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_superadmin)])
async def create_user(body: UserCreate, db: AsyncSession = Depends(get_db)):
    # Check uniqueness
    existing = await db.execute(select(AdminUser).where(AdminUser.username == body.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username already exists")

    user = AdminUser(
        username=body.username,
        email=body.email,
        hashed_password=hash_password(body.password),
        is_superadmin=body.is_superadmin,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@router.get("/{user_id}", response_model=AdminUserResponse)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    user = await db.get(AdminUser, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/{user_id}", response_model=AdminUserResponse,
              dependencies=[Depends(require_superadmin)])
async def update_user(user_id: int, body: UserUpdate, db: AsyncSession = Depends(get_db)):
    user = await db.get(AdminUser, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    updates = body.model_dump(exclude_unset=True)
    if "password" in updates:
        user.hashed_password = hash_password(updates.pop("password"))
    for field, value in updates.items():
        setattr(user, field, value)
    await db.flush()
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_superadmin)])
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db)):
    user = await db.get(AdminUser, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await db.delete(user)
