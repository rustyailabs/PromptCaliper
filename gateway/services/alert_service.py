"""Alert evaluation and event persistence backed by Firestore."""
import logging
from datetime import datetime, timezone

from gateway.firestore_store import FirestoreObject, FirestoreStore

logger = logging.getLogger(__name__)


class AlertService:
    def __init__(self, db: FirestoreStore):
        self.db = db

    async def evaluate_all_rules(self) -> None:
        # Kept intentionally small for the Firestore cutover; budget alerts still
        # fire synchronously from the budget callback below.
        return

    async def fire_budget_alert(self, key: FirestoreObject, current: float, limit: float) -> None:
        message = f"Virtual key {key.key_prefix} budget exceeded: ${current:.4f} / ${limit:.4f}"
        self.db.create("alert_events", {
            "rule_id": None,
            "rule_name": "Virtual key budget",
            "metric": "budget_remaining_usd",
            "actual_value": current,
            "threshold_value": limit,
            "message": message,
            "fired_at": datetime.now(timezone.utc),
        })
        logger.warning(message)
