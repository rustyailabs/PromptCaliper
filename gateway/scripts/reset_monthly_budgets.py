"""
Reset all virtual key monthly spend counters.
Intended to run on the 1st of each month via APScheduler or cron.

Usage:
    python -m gateway.scripts.reset_monthly_budgets
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from gateway.firestore_store import store, utcnow


async def reset():
    now = utcnow()
    print(f"[reset_monthly_budgets] Running at {now.isoformat()}")

    keys = store.list("virtual_keys")
    for key in keys:
        key.current_spend_usd = 0.0
        key.budget_reset_at = now
        store.save(key)

    print(f"[reset_monthly_budgets] Reset {len(keys)} virtual key(s).")
    print("[reset_monthly_budgets] Done.")


if __name__ == "__main__":
    asyncio.run(reset())
