"""
Pre-call budget enforcement callback.
Runs before every LiteLLM API call to check spend limits.

NOTE: This callback runs *outside* FastAPI's request/response cycle.
      Never raise HTTPException here — it will not produce an HTTP response
      and will be swallowed as an unhandled 500.  Use plain Python exceptions
      that the gateway router catches explicitly.
"""
import logging

from litellm.integrations.custom_logger import CustomLogger

logger = logging.getLogger(__name__)


class BudgetExceededError(Exception):
    """Raised when a virtual key's monthly budget has been exhausted."""
    def __init__(self, message: str, status_code: int = 429):
        super().__init__(message)
        self.status_code = status_code


class KeyInactiveError(Exception):
    """Raised when the virtual key has been deactivated."""
    def __init__(self, message: str, status_code: int = 403):
        super().__init__(message)
        self.status_code = status_code


class BudgetEnforcementCallback(CustomLogger):

    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        from gateway.db.session import get_db_context
        from gateway.services.alert_service import AlertService

        metadata = data.get("metadata") or {}
        virtual_key_id = metadata.get("virtual_key_id")

        if not virtual_key_id:
            return  # Admin/unkeyed call — skip budget check

        async with get_db_context() as db:
            key = db.get("virtual_keys", virtual_key_id)
            if not key:
                return

            if not key.is_active:
                raise KeyInactiveError("Virtual key is inactive")

            if key.monthly_budget_usd is None:
                return  # No budget set — allow

            current = float(key.current_spend_usd or 0)
            limit = float(key.monthly_budget_usd)

            if current >= limit:
                action = key.budget_action or "block"

                if action in ("alert", "both"):
                    # Fire alert asynchronously — don't block the request
                    try:
                        await AlertService(db).fire_budget_alert(key, current, limit)
                    except Exception as exc:
                        logger.error("Alert firing failed: %s", exc)

                if action in ("block", "both"):
                    logger.warning(
                        "Key %s budget exceeded: $%.4f / $%.4f — blocking request.",
                        key.key_prefix, current, limit,
                    )
                    raise BudgetExceededError(
                        f"Monthly budget exceeded (${current:.4f} / ${limit:.4f}). Contact your admin."
                    )
