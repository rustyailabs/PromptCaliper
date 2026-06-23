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
    content: str | list[dict[str, Any]] = Field(...)


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[Message] = Field(..., min_length=1, max_length=100)
    temperature: float | None = None
    max_tokens: int | None = None
    stream: bool = False
    response_modalities: list[str] | None = None


async def _authenticate_and_rate_limit(
    request: Request,
    model: str,
    db: FirestoreStore,
) -> tuple[Any, Any]:
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
        if virtual_key.allowed_models and model not in virtual_key.allowed_models:
            raise HTTPException(
                status_code=403,
                detail=f"Model '{model}' not permitted for this key. Allowed: {virtual_key.allowed_models}",
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

    # Rate limiting (DB-backed, survives restarts)
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
            await _persist_blocked_request(virtual_key.id, team_id, model, 429)
            retry_after = 60 - now_utc.second
            raise HTTPException(
                status_code=429,
                headers={"Retry-After": str(retry_after)},
                detail=(
                    f"Rate limit exceeded: {virtual_key.rpm_limit} RPM. "
                    f"Used {current_rpm}/{virtual_key.rpm_limit} requests this minute."
                ),
            )

    return virtual_key, team_id


@router.post("/chat/completions")
async def chat_completions(
    body: ChatCompletionRequest,
    request: Request,
    db: FirestoreStore = Depends(get_db),
    litellm_service=Depends(get_litellm_service),
) -> Any:
    # ── 1. Authentication & Rate limiting ────────────────────────────────────
    virtual_key, team_id = await _authenticate_and_rate_limit(request, body.model, db)

    # ── 2. Input guardrails ───────────────────────────────────────────────────
    messages = [m.model_dump() for m in body.messages]

    # Skip input guardrails for multimodal messages (image content can't be scanned as text)
    has_multimodal = any(isinstance(m.get("content"), list) for m in messages)
    if has_multimodal:
        guardrail_triggered = False
        _input_triggered_by = []
    else:
        messages, guardrail_triggered, _input_triggered_by = await apply_input_guardrails(messages, db)

    # ── 3. LiteLLM completion ─────────────────────────────────────────────────
    kwargs: dict[str, Any] = {}
    if body.temperature is not None:
        kwargs["temperature"] = body.temperature
    if body.max_tokens is not None:
        kwargs["max_tokens"] = body.max_tokens
    if body.response_modalities is not None:
        kwargs["response_modalities"] = body.response_modalities

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

    # ── 4. Output guardrails ──────────────────────────────────────────────────
    # Skip guardrail text scanning for multimodal responses (image data in content list)
    if response and response.choices:
        content = response.choices[0].message.content or ""
        if isinstance(content, str) and content:
            processed_content, out_triggered, out_triggered_by = await apply_output_guardrails(content, db)
            if out_triggered:
                response.choices[0].message.content = processed_content
                guardrail_triggered = True

    # ── 5. Build response — signal guardrail activity to the caller ───────────
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


# ── Image Generation ──────────────────────────────────────────────────────────
class ImageGenerationRequest(BaseModel):
    prompt: str = Field(..., max_length=10_000)
    model: str
    n: int | None = 1
    size: str | None = "1024x1024"
    response_format: Literal["url", "b64_json"] | None = "url"
    source_image: str | None = None
    source_mime_type: str | None = None


@router.post("/images/generations")
async def images_generations(
    body: ImageGenerationRequest,
    request: Request,
    db: FirestoreStore = Depends(get_db),
    litellm_service=Depends(get_litellm_service),
) -> Any:
    virtual_key, team_id = await _authenticate_and_rate_limit(request, body.model, db)

    kwargs: dict[str, Any] = {}
    if body.n is not None:
        kwargs["n"] = body.n
    if body.size is not None:
        kwargs["size"] = body.size
    if body.response_format is not None:
        kwargs["response_format"] = body.response_format

    try:
        response = await litellm_service.generate_image(
            prompt=body.prompt,
            model=body.model,
            virtual_key_id=virtual_key.id if virtual_key else None,
            team_id=team_id,
            source_base64=body.source_image,
            mime_type=body.source_mime_type,
            **kwargs,
        )
        try:
            response_dict = response.model_dump()
        except Exception:
            response_dict = dict(response)
        return JSONResponse(content=response_dict)
    except (BudgetExceededError, KeyInactiveError) as exc:
        if virtual_key:
            await _persist_blocked_request(virtual_key.id, team_id, body.model, exc.status_code)
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("LiteLLM image generation failed for model '%s'", body.model)
        raise HTTPException(status_code=502, detail=f"Upstream model error: {exc}") from exc


# ── Video Generation ──────────────────────────────────────────────────────────
class VideoGenerationRequest(BaseModel):
    prompt: str = Field(..., max_length=10_000)
    model: str
    duration_seconds: int | None = None
    fps: int | None = None
    aspect_ratio: str | None = None
    wait_for_completion: bool = False


@router.post("/videos/generations")
async def videos_generations(
    body: VideoGenerationRequest,
    request: Request,
    db: FirestoreStore = Depends(get_db),
    litellm_service=Depends(get_litellm_service),
) -> Any:
    virtual_key, team_id = await _authenticate_and_rate_limit(request, body.model, db)

    kwargs: dict[str, Any] = {}
    if body.duration_seconds is not None:
        kwargs["duration_seconds"] = body.duration_seconds
    if body.fps is not None:
        kwargs["fps"] = body.fps
    if body.aspect_ratio is not None:
        kwargs["aspect_ratio"] = body.aspect_ratio

    try:
        response = await litellm_service.generate_video(
            prompt=body.prompt,
            model=body.model,
            **kwargs,
        )
        
        if body.wait_for_completion:
            import asyncio
            video_id = getattr(response, "id", None) or response.get("id")
            if video_id:
                # Poll every 5 seconds for a maximum of 5 minutes (60 iterations)
                max_polls = 60
                for _ in range(max_polls):
                    await asyncio.sleep(5)
                    try:
                        status_obj = await litellm_service.get_video_status(video_id=video_id)
                        status = getattr(status_obj, "status", None)
                        if not status and isinstance(status_obj, dict):
                            status = status_obj.get("status")
                        
                        if status in ["completed", "failed", "succeeded"]:
                            download_url = f"{request.base_url}api/v1/videos/generations/{video_id}/content"
                            return JSONResponse(content={
                                "id": video_id,
                                "object": "video",
                                "status": status,
                                "model": body.model,
                                "data": [{"url": download_url}]
                            })
                    except Exception as poll_exc:
                        logger.warning("Error during video status poll: %s", poll_exc)
                # If we timeout, return the latest response/status we have
                try:
                    response_dict = response.model_dump()
                except Exception:
                    response_dict = dict(response)
                return JSONResponse(content=response_dict)

        try:
            response_dict = response.model_dump()
        except Exception:
            response_dict = dict(response)
        return JSONResponse(content=response_dict)
    except (BudgetExceededError, KeyInactiveError) as exc:
        if virtual_key:
            await _persist_blocked_request(virtual_key.id, team_id, body.model, exc.status_code)
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("LiteLLM video generation failed for model '%s'", body.model)
        raise HTTPException(status_code=502, detail=f"Upstream model error: {exc}") from exc


@router.get("/videos/generations/{id}")
async def get_video_status(
    id: str,
    request: Request,
    db: FirestoreStore = Depends(get_db),
    litellm_service=Depends(get_litellm_service),
) -> Any:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer sk-ft-"):
        raw_key = auth_header.split(" ", 1)[1]
        virtual_key = await validate_key(raw_key, db)
        if virtual_key is None:
            raise HTTPException(status_code=401, detail="Invalid or expired virtual key")
    elif auth_header.startswith("Bearer "):
        get_current_user(request, db)
    else:
        raise HTTPException(status_code=401, detail="Authorization header required (Bearer token)")

    try:
        response = await litellm_service.get_video_status(video_id=id)
        status = getattr(response, "status", None)
        if not status and isinstance(response, dict):
            status = response.get("status")
            
        if status in ["completed", "succeeded"]:
            download_url = f"{request.base_url}api/v1/videos/generations/{id}/content"
            model_name = getattr(response, "model", None)
            if not model_name and isinstance(response, dict):
                model_name = response.get("model")
            return JSONResponse(content={
                "id": id,
                "object": "video",
                "status": status,
                "model": model_name or "veo-3.1-lite",
                "data": [{"url": download_url}]
            })

        try:
            response_dict = response.model_dump()
        except Exception:
            response_dict = dict(response)
        return JSONResponse(content=response_dict)
    except Exception as exc:
        logger.exception("LiteLLM video status failed for job '%s'", id)
        raise HTTPException(status_code=502, detail=f"Upstream status error: {exc}")


@router.get("/videos/generations/{id}/content")
async def get_video_content(
    id: str,
    request: Request,
    db: FirestoreStore = Depends(get_db),
    litellm_service=Depends(get_litellm_service),
) -> Any:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer sk-ft-"):
        raw_key = auth_header.split(" ", 1)[1]
        virtual_key = await validate_key(raw_key, db)
        if virtual_key is None:
            raise HTTPException(status_code=401, detail="Invalid or expired virtual key")
    elif auth_header.startswith("Bearer "):
        get_current_user(request, db)
    else:
        raise HTTPException(status_code=401, detail="Authorization header required (Bearer token)")

    try:
        response = await litellm_service.get_video_content(video_id=id)
        if isinstance(response, bytes):
            from fastapi import Response
            return Response(content=response, media_type="video/mp4")
        try:
            response_dict = response.model_dump()
        except Exception:
            response_dict = dict(response)
        return JSONResponse(content=response_dict)
    except Exception as exc:
        logger.exception("LiteLLM video content failed for job '%s'", id)
        raise HTTPException(status_code=502, detail=f"Upstream content error: {exc}")
