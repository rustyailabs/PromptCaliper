"""Virtual key generation, hashing, and validation."""
import hashlib
import secrets
from datetime import datetime, timezone

from gateway.firestore_store import FirestoreObject, FirestoreStore


def generate_virtual_key() -> tuple[str, str, str]:
    """
    Returns (full_key, key_hash, key_prefix).
    Full key is returned ONCE at creation time only — never stored.
    """
    raw = "sk-ft-" + secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    key_prefix = raw[:10] + "..." + raw[-4:]
    return raw, key_hash, key_prefix


def hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


async def validate_key(raw_key: str, db: FirestoreStore) -> FirestoreObject | None:
    key_hash = hash_key(raw_key)
    key = db.first("virtual_keys", key_hash=key_hash, is_active=True)

    if key is None:
        return None

    # Check expiry
    if key.expires_at and key.expires_at < datetime.now(timezone.utc):
        return None

    return key
