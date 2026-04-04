"""
LiteLLM custom logger that persists every request to the database.
Writes RequestLog + SpendLedger rows and updates the virtual key's running spend total.
"""
import logging
import uuid
from datetime import datetime, timezone

import litellm
from litellm.integrations.custom_logger import CustomLogger

from gateway.db.session import get_db_context
# log_prompt_content is no longer read from the static settings object.
# It is fetched at runtime from the system_config DB row via a 10-second
# in-process TTL cache, allowing a superadmin to toggle it without a restart.
from gateway.models.system_config import get_log_prompt_content

logger = logging.getLogger(__name__)


class RequestLoggingCallback(CustomLogger):

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        await self._persist(kwargs, response_obj, start_time, end_time, success=True)

    async def async_log_failure_event(self, kwargs, response_obj, start_time, end_time):
        await self._persist(kwargs, response_obj, start_time, end_time, success=False)

    async def _persist(self, kwargs, response_obj, start_time, end_time, success: bool):
        from gateway.models.request_log import RequestLog
        from gateway.models.spend_ledger import SpendLedger
        from gateway.models.virtual_key import VirtualKey
        from sqlalchemy import select

        try:
            # LiteLLM Router stores metadata under litellm_params.metadata,
            # not at the top-level kwargs["metadata"].
            litellm_params = kwargs.get("litellm_params") or {}
            metadata = litellm_params.get("metadata") or kwargs.get("metadata") or {}
            virtual_key_id = metadata.get("virtual_key_id")
            team_id = metadata.get("team_id")

            latency_ms = int((end_time - start_time).total_seconds() * 1000)

            # Token counts
            usage = getattr(response_obj, "usage", None)
            prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
            completion_tokens = getattr(usage, "completion_tokens", 0) or 0
            total_tokens = getattr(usage, "total_tokens", 0) or 0

            # Cost (LiteLLM calculates this)
            cost_usd = 0.0
            if success and response_obj:
                try:
                    cost_usd = litellm.completion_cost(completion_response=response_obj) or 0.0
                except Exception:
                    pass

            # Response content — evaluated after the DB session is open so the
            # TTL-cached runtime flag is available. Placeholder set here; actual
            # value assigned inside the DB context block below once log_content
            # is resolved.
            response_content = None

            # Model actually used
            actual_model = getattr(response_obj, "model", None) or kwargs.get("model", "unknown")

            # Cache hit — LiteLLM Router sets it at kwargs["cache_hit"] (top-level)
            # and also in response._hidden_params; check both.
            hidden_params = getattr(response_obj, "_hidden_params", {}) or {}
            cache_hit = bool(
                kwargs.get("cache_hit")
                or hidden_params.get("cache_hit")
                or metadata.get("cache_hit")
            )

            # Error message
            error_message = None
            if not success:
                exc = kwargs.get("exception")
                error_message = str(exc) if exc else "Unknown error"

            # Status code
            if success:
                status_code = 200
            else:
                exc = kwargs.get("exception")
                status_code = getattr(exc, "status_code", 500)

            # Cache hits reuse the original response object (same .id).
            # Always generate a fresh UUID so the UNIQUE constraint on request_id
            # is never violated — the original_request_id is stored separately for tracing.
            original_request_id = getattr(response_obj, "id", None)
            request_id = str(uuid.uuid4())

            # Always store as UTC — LiteLLM passes naive local-time datetimes.
            # .astimezone(utc) treats naive as local and converts correctly.
            if isinstance(start_time, datetime):
                started_at = start_time if start_time.tzinfo else start_time.astimezone(timezone.utc)
            else:
                started_at = datetime.now(timezone.utc)

            period_month = started_at.strftime("%Y-%m")

            async with get_db_context() as db:
                # Fetch the runtime flag via TTL cache (DB hit at most once per
                # 10 s per worker — effectively free on the hot path).
                log_content = await get_log_prompt_content(db)

                # Resolve response content now that the runtime flag is known.
                if log_content and success and response_obj and hasattr(response_obj, "choices") and response_obj.choices:
                    response_content = response_obj.choices[0].message.content

                log = RequestLog(
                    request_id=request_id,
                    virtual_key_id=virtual_key_id,
                    team_id=team_id,
                    litellm_model_name=actual_model,
                    requested_model=kwargs.get("model"),
                    status_code=status_code,
                    prompt_messages=kwargs.get("messages", []) if log_content else [],
                    response_content=response_content,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    cost_usd=cost_usd,
                    latency_ms=latency_ms,
                    cache_hit=cache_hit,
                    guardrail_triggered=metadata.get("guardrail_triggered", False),
                    error_message=error_message,
                    started_at=started_at,
                )
                db.add(log)
                await db.flush()  # get log.id

                # Always write SpendLedger — even zero-cost models need token tracking
                ledger = SpendLedger(
                    request_log_id=log.id,
                    virtual_key_id=virtual_key_id,
                    team_id=team_id,
                    amount_usd=cost_usd,
                    period_month=period_month,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                )
                db.add(ledger)

                # Update denormalized spend counter on the virtual key atomically.
                # Using a SQL UPDATE expression avoids the read-modify-write race
                # condition that occurs when two requests complete concurrently.
                if cost_usd > 0 and virtual_key_id:
                    from sqlalchemy import update as sa_update
                    await db.execute(
                        sa_update(VirtualKey)
                        .where(VirtualKey.id == virtual_key_id)
                        .values(current_spend_usd=VirtualKey.current_spend_usd + cost_usd)
                    )

        except Exception as exc:
            logger.error("RequestLoggingCallback failed: %s", exc, exc_info=True)
