"""
Seed or reset the superadmin account.

Usage:
    python -m gateway.scripts.seed_admin
    # or to reset password:
    SUPERADMIN_PASSWORD=newpass python -m gateway.scripts.seed_admin
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from gateway.auth.service import hash_password
from gateway.config import settings
from gateway.firestore_store import store


async def seed():
    existing = store.first("admin_users", username=settings.SUPERADMIN_USERNAME)

    if existing:
        existing.hashed_password = hash_password(settings.SUPERADMIN_PASSWORD)
        existing.is_active = True
        existing.is_superadmin = True
        store.save(existing)
        print(f"[seed_admin] Updated password for existing superadmin: {settings.SUPERADMIN_USERNAME}")
    else:
        store.create("admin_users", {
            "username": settings.SUPERADMIN_USERNAME,
            "email": settings.SUPERADMIN_EMAIL,
            "hashed_password": hash_password(settings.SUPERADMIN_PASSWORD),
            "is_active": True,
            "is_superadmin": True,
            "last_login_at": None,
        })
        print(f"[seed_admin] Created superadmin: {settings.SUPERADMIN_USERNAME}")

    print("[seed_admin] Done.")


if __name__ == "__main__":
    asyncio.run(seed())
