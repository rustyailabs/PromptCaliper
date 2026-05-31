import time
from collections import defaultdict
from datetime import datetime, timezone
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import JWTError

from gateway.auth.schemas import AdminUserResponse, LoginRequest, RefreshRequest, TokenResponse
from gateway.auth.service import (
    authenticate_user,
    blocklist_token,
    create_access_token,
    create_refresh_token,
    decode_token,
    is_token_blocklisted,
)
from gateway.db.session import get_db
from gateway.dependencies import get_current_user
from gateway.firestore_store import FirestoreObject, FirestoreStore

router = APIRouter()

# ── In-process login rate limiter ────────────────────────────────────────────
# Tracks (ip → list[attempt_timestamp]) for a sliding-window check.
# For multi-worker deployments replace with Redis-backed counters.
_LOGIN_ATTEMPTS: dict[str, list[float]] = defaultdict(list)
_LOGIN_LOCK = Lock()
_LOGIN_WINDOW_SECONDS = 60
_LOGIN_MAX_ATTEMPTS = 10  # per IP per window


def _check_login_rate_limit(ip: str) -> None:
    """Raise 429 if the IP has exceeded the login attempt threshold."""
    now = time.monotonic()
    window_start = now - _LOGIN_WINDOW_SECONDS
    with _LOGIN_LOCK:
        attempts = _LOGIN_ATTEMPTS[ip]
        # Prune timestamps outside the window
        attempts[:] = [t for t in attempts if t >= window_start]
        if len(attempts) >= _LOGIN_MAX_ATTEMPTS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Too many login attempts. "
                    f"Maximum {_LOGIN_MAX_ATTEMPTS} attempts per {_LOGIN_WINDOW_SECONDS}s window."
                ),
                headers={"Retry-After": str(_LOGIN_WINDOW_SECONDS)},
            )
        attempts.append(now)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, db: FirestoreStore = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    _check_login_rate_limit(client_ip)

    user = authenticate_user(body.username, body.password, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    user.last_login_at = datetime.now(timezone.utc)
    db.save(user)

    access_token = create_access_token(user.id)
    refresh_token, jti = create_refresh_token(user.id)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: FirestoreStore = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not a refresh token")

    jti = payload.get("jti")
    if jti and is_token_blocklisted(jti, db):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked")

    user_id = int(payload["sub"])
    user = db.get("admin_users", user_id)
    if not user or not getattr(user, "is_active", False):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    access_token = create_access_token(user.id)
    new_refresh_token, new_jti = create_refresh_token(user.id)

    # Blocklist old refresh token
    if jti:
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        blocklist_token(jti, exp, db)

    return TokenResponse(access_token=access_token, refresh_token=new_refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(body: RefreshRequest, db: FirestoreStore = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token)
        jti = payload.get("jti")
        if jti:
            exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
            blocklist_token(jti, exp, db)
    except JWTError:
        pass  # token already invalid — logout is idempotent


@router.get("/me", response_model=AdminUserResponse)
def me(current_user: FirestoreObject = Depends(get_current_user)):
    return current_user
