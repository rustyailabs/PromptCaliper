from fastapi import Depends, HTTPException, Request, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.auth.service import decode_token
from gateway.db.session import get_db
from gateway.models.admin_user import AdminUser


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AdminUser:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    token = auth_header.split(" ", 1)[1]
    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not an access token")

    user_id = int(payload["sub"])
    result = await db.execute(select(AdminUser).where(AdminUser.id == user_id, AdminUser.is_active == True))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user


async def require_superadmin(
    current_user: AdminUser = Depends(get_current_user),
) -> AdminUser:
    """Dependency that requires the caller to be a superadmin. Use on write endpoints."""
    if not current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superadmin privileges required",
        )
    return current_user


def get_litellm_service(request: Request):
    """Inject the singleton LiteLLMService from app state."""
    return request.app.state.litellm_service
