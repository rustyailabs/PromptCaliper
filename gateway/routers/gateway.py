"""
OpenAI-compatible gateway endpoint.
Validates virtual key → applies rate limits → runs guardrails → calls LiteLLM → applies output guardrails.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from gateway.callbacks.budget_callback import BudgetExceededError, KeyInactiveError
from gateway.config import settings
from gateway.db.session import get_db
from gateway.dependencies import get_current_user, get_litellm_service
from gateway.firestore_store import FirestoreStore
from gateway.services.guardrail_service import apply_input_guardrails, apply_output_guardrails
from gateway.services.key_service import validate_key

logger = logging.getLogger(__name__)
router = APIRouter()


async def _persist_blocked_request(
    virtual_key_id: int,
    team_id: Any,
    model: str,
    status_code: int,
) -> None:
    """Write a RequestLog row for requests blocked before reaching LiteLLM.

    Uses an independent DB session so the row is committed regardless of what
    happens to the request-scoped session (which is rolled back on exceptions).
    """
    from gateway.firestore_store import store

    try:
        now = datetime.now(timezone.utc)
        store.create("request_logs", {
            "request_id": str(uuid.uuid4()),
            "virtual_key_id": virtual_key_id,
            "team_id": team_id,
            "litellm_model_name": model,
            "requested_model": model,
            "status_code": status_code,
            "prompt_messages": [],
            "response_content": None,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost_usd": 0,
            "latency_ms": 0,
            "cache_hit": False,
            "guardrail_triggered": False,
            "error_message": None,
            "started_at": now,
        })
    except Exception as exc:
        logger.error("Failed to log blocked request: %s", exc)


class Message(BaseModel):
    role: str
    content: str = Field(..., max_length=100_000)


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[Message] = Field(..., min_length=1, max_length=100)
    temperature: float | None = None
    max_tokens: int | None = None
    stream: bool = False


@router.post("/chat/completions")
async def chat_completions(
    body: ChatCompletionRequest,
    request: Request,
    db: FirestoreStore = Depends(get_db),
    litellm_service=Depends(get_litellm_service),
) -> Any:
    # ── 1. Authentication ─────────────────────────────────────────────────────
    virtual_key = None
    team_id = None
    auth_header = request.headers.get("Authorization", "")

    if auth_header.startswith("Bearer sk-ft-"):
        # Virtual key path
        raw_key = auth_header.split(" ", 1)[1]
        virtual_key = await validate_key(raw_key, db)
        if virtual_key is None:
            raise HTTPException(status_code=401, detail="Invalid or expired virtual key")

        # Enforce allowed models
        if virtual_key.allowed_models and body.model not in virtual_key.allowed_models:
            raise HTTPException(
                status_code=403,
                detail=f"Model '{body.model}' not permitted for this key. Allowed: {virtual_key.allowed_models}",
            )

        team_id = virtual_key.team_id

    elif auth_header.startswith("Bearer "):
        # Admin JWT path — validate the token properly
        try:
            get_current_user(request, db)
        except HTTPException:
            raise  # Re-raise 401/403 from get_current_user as-is
    else:
        raise HTTPException(status_code=401, detail="Authorization header required (Bearer token)")

    # ── 2. Rate limiting (DB-backed, survives restarts) ───────────────────────
    if virtual_key and virtual_key.rpm_limit:
        now_utc = datetime.now(timezone.utc)
        minute_start = now_utc.replace(second=0, microsecond=0)
        current_rpm = len([
            log for log in db.where("request_logs", virtual_key_id=virtual_key.id)
            if log.started_at >= minute_start
        ])
        if current_rpm >= virtual_key.rpm_limit:
            # Persist the blocked request using a separate session so it commits
            # even though we are about to raise an exception in this session.
            await _persist_blocked_request(virtual_key.id, team_id, body.model, 429)
            retry_after = 60 - now_utc.second
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(retry_after)},
                content={
                    "detail": (
                        f"Rate limit exceeded: {virtual_key.rpm_limit} RPM. "
                        f"Used {current_rpm}/{virtual_key.rpm_limit} requests this minute."
                    )
                },
            )

    # ── 3. Input guardrails ───────────────────────────────────────────────────
    messages = [m.model_dump() for m in body.messages]
    messages, guardrail_triggered, _input_triggered_by = await apply_input_guardrails(messages, db)

    # ── 4. LiteLLM completion ─────────────────────────────────────────────────
    kwargs: dict[str, Any] = {}
    if body.temperature is not None:
        kwargs["temperature"] = body.temperature
    if body.max_tokens is not None:
        kwargs["max_tokens"] = body.max_tokens

    try:
        response = await litellm_service.complete(
            messages=messages,
            model=body.model,
            virtual_key_id=virtual_key.id if virtual_key else None,
            team_id=team_id,
            extra_metadata={"guardrail_triggered": guardrail_triggered},
            **kwargs,
        )
    except (BudgetExceededError, KeyInactiveError) as exc:
        # Budget callback raises these custom exceptions — map to correct HTTP codes
        if virtual_key:
            await _persist_blocked_request(virtual_key.id, team_id, body.model, exc.status_code)
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except RuntimeError as exc:
        # e.g. "LiteLLM Router not initialized. Add at least one active model."
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("LiteLLM completion failed for model '%s'", body.model)
        raise HTTPException(status_code=502, detail=f"Upstream model error: {exc}") from exc

    # ── 5. Output guardrails ──────────────────────────────────────────────────
    if response and response.choices:
        content = response.choices[0].message.content or ""
        processed_content, out_triggered, out_triggered_by = await apply_output_guardrails(content, db)
        if out_triggered:
            response.choices[0].message.content = processed_content
            guardrail_triggered = True

    # ── 6. Build response — signal guardrail activity to the caller ───────────
    # Convert the LiteLLM ModelResponse to a dict so we can add gateway metadata
    # without breaking OpenAI-compatible clients (they ignore unknown keys).
    try:
        response_dict = response.model_dump()
    except Exception:
        response_dict = dict(response)

    response_dict["_gateway"] = {
        "guardrail_triggered": guardrail_triggered,
    }

    headers = {}
    if guardrail_triggered:
        headers["X-Guardrail-Triggered"] = "true"

    return JSONResponse(content=response_dict, headers=headers)
