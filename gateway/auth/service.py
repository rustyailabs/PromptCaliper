import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from gateway.config import settings
from gateway.firestore_store import FirestoreObject, FirestoreStore

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


def authenticate_user(username: str, password: str, db: FirestoreStore) -> FirestoreObject | None:
    user = db.first("admin_users", username=username)
    if not user or not getattr(user, "is_active", False) or not verify_password(password, user.hashed_password):
        return None
    return user


def is_token_blocklisted(jti: str, db: FirestoreStore) -> bool:
    return db.first("refresh_token_blocklist", jti=jti) is not None


def blocklist_token(jti: str, expires_at: datetime, db: FirestoreStore) -> None:
    db.create("refresh_token_blocklist", {"jti": jti, "expires_at": expires_at})
