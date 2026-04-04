import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.config import settings
from gateway.models.admin_user import AdminUser, RefreshTokenBlocklist

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "type": "access", "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: int) -> tuple[str, str]:
    """Returns (encoded_token, jti)"""
    jti = str(uuid.uuid4())
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": str(user_id), "type": "refresh", "jti": jti, "exp": expire}
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, jti


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


async def authenticate_user(username: str, password: str, db: AsyncSession) -> AdminUser | None:
    result = await db.execute(select(AdminUser).where(AdminUser.username == username, AdminUser.is_active == True))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


async def is_token_blocklisted(jti: str, db: AsyncSession) -> bool:
    result = await db.execute(
        select(RefreshTokenBlocklist).where(RefreshTokenBlocklist.jti == jti)
    )
    return result.scalar_one_or_none() is not None


async def blocklist_token(jti: str, expires_at: datetime, db: AsyncSession) -> None:
    entry = RefreshTokenBlocklist(jti=jti, expires_at=expires_at)
    db.add(entry)
    await db.flush()
