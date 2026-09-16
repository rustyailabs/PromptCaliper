from fastapi import Depends, HTTPException, Request, status
from jose import JWTError

from gateway.auth.service import decode_token
from gateway.db.session import get_db
from gateway.firestore_store import FirestoreObject, FirestoreStore


def get_current_user(
    request: Request,
    db: FirestoreStore = Depends(get_db),
) -> FirestoreObject:
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
    user = db.get("admin_users", user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not getattr(user, "is_active", False):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user


async def require_superadmin(
    current_user: FirestoreObject = Depends(get_current_user),
) -> FirestoreObject:
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
