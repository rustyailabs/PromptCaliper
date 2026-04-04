"""
Seed or reset the superadmin account.

Usage:
    python -m gateway.scripts.seed_admin
    # or to reset password:
    SUPERADMIN_PASSWORD=newpass python -m gateway.scripts.seed_admin
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from gateway.config import settings
from gateway.db.base import build_engine
from gateway.db.session import AsyncSessionLocal
from gateway.models.admin_user import AdminUser
from gateway.auth.service import hash_password
from sqlalchemy import select, text


async def seed():
    engine = build_engine(str(settings.DATABASE_URL))

    # Ensure tables exist
    from gateway.db.base import Base
    import gateway.models  # noqa: F401 — registers all models
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AdminUser).where(AdminUser.username == settings.SUPERADMIN_USERNAME)
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.hashed_password = hash_password(settings.SUPERADMIN_PASSWORD)
            existing.is_active = True
            existing.is_superadmin = True
            print(f"[seed_admin] Updated password for existing superadmin: {settings.SUPERADMIN_USERNAME}")
        else:
            admin = AdminUser(
                username=settings.SUPERADMIN_USERNAME,
                email=settings.SUPERADMIN_EMAIL,
                hashed_password=hash_password(settings.SUPERADMIN_PASSWORD),
                is_active=True,
                is_superadmin=True,
            )
            db.add(admin)
            print(f"[seed_admin] Created superadmin: {settings.SUPERADMIN_USERNAME}")

        await db.commit()
    print("[seed_admin] Done.")


if __name__ == "__main__":
    asyncio.run(seed())
