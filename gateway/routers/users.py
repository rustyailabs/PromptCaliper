from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr

from gateway.auth.schemas import AdminUserResponse
from gateway.auth.service import hash_password
from gateway.db.session import get_db
from gateway.dependencies import get_current_user, require_superadmin
from gateway.firestore_store import FirestoreStore
from gateway.models.system_config import invalidate_log_prompt_content_cache

router = APIRouter(dependencies=[Depends(get_current_user)])


class RuntimeSettings(BaseModel):
    log_prompt_content: bool


@router.get("/runtime-settings", response_model=RuntimeSettings, dependencies=[Depends(require_superadmin)])
async def get_runtime_settings(db: FirestoreStore = Depends(get_db)) -> RuntimeSettings:
    config = db.get("system_config", 1)
    return RuntimeSettings(log_prompt_content=config.log_prompt_content if config else False)


@router.patch("/runtime-settings", response_model=RuntimeSettings, dependencies=[Depends(require_superadmin)])
async def update_runtime_settings(body: RuntimeSettings, db: FirestoreStore = Depends(get_db)) -> RuntimeSettings:
    config = db.get("system_config", 1)
    if not config:
        config = db.set("system_config", 1, body.model_dump())
    else:
        config.log_prompt_content = body.log_prompt_content
        db.save(config)
    invalidate_log_prompt_content_cache()
    return RuntimeSettings(log_prompt_content=config.log_prompt_content)


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    is_superadmin: bool = False


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    password: str | None = None
    is_superadmin: bool | None = None
    is_active: bool | None = None


@router.get("", response_model=list[AdminUserResponse])
def list_users(db: FirestoreStore = Depends(get_db)):
    return db.list("admin_users", order_by="username")


@router.post("", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_superadmin)])
async def create_user(body: UserCreate, db: FirestoreStore = Depends(get_db)):
    if db.first("admin_users", username=body.username):
        raise HTTPException(status_code=409, detail="Username already exists")
    return db.create("admin_users", {
        "username": body.username,
        "email": body.email,
        "hashed_password": hash_password(body.password),
        "is_superadmin": body.is_superadmin,
        "is_active": True,
        "last_login_at": None,
    })


@router.get("/{user_id}", response_model=AdminUserResponse)
async def get_user(user_id: int, db: FirestoreStore = Depends(get_db)):
    user = db.get("admin_users", user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/{user_id}", response_model=AdminUserResponse, dependencies=[Depends(require_superadmin)])
async def update_user(user_id: int, body: UserUpdate, db: FirestoreStore = Depends(get_db)):
    user = db.get("admin_users", user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    updates = body.model_dump(exclude_unset=True)
    if "password" in updates:
        user.hashed_password = hash_password(updates.pop("password"))
    for field, value in updates.items():
        setattr(user, field, value)
    return db.save(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_superadmin)])
async def delete_user(user_id: int, db: FirestoreStore = Depends(get_db)):
    if not db.get("admin_users", user_id):
        raise HTTPException(status_code=404, detail="User not found")
    db.delete("admin_users", user_id)
