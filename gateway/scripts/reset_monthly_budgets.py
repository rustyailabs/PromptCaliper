"""
Reset all virtual key monthly spend counters.
Intended to run on the 1st of each month via APScheduler or cron.

Usage:
    python -m gateway.scripts.reset_monthly_budgets
"""
import asyncio
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from gateway.db.session import AsyncSessionLocal
from gateway.models.virtual_key import VirtualKey
from sqlalchemy import select, update


async def reset():
    now = datetime.now(timezone.utc)
    print(f"[reset_monthly_budgets] Running at {now.isoformat()}")

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            update(VirtualKey)
            .values(
                current_spend_usd=0.0,
                budget_reset_at=now,
            )
            .returning(VirtualKey.id)
        )
        rows = result.fetchall()
        await db.commit()
        print(f"[reset_monthly_budgets] Reset {len(rows)} virtual key(s).")

    print("[reset_monthly_budgets] Done.")


if __name__ == "__main__":
    asyncio.run(reset())
