"""PromptCaliper AI Gateway — FastAPI application factory."""
import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from sqlalchemy import select, text

from gateway.auth.router import router as auth_router
from gateway.callbacks.budget_callback import BudgetEnforcementCallback
from gateway.callbacks.logging_callback import RequestLoggingCallback
from gateway.config import settings
from gateway.db.base import Base, engine
from gateway.db.session import AsyncSessionLocal
from gateway.routers.gateway import router as gateway_router
from gateway.services.cache_service import apply_cache_config
from gateway.services.litellm_service import LiteLLMService

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def _create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ensured.")


async def _seed_superadmin() -> None:
    from gateway.auth.service import hash_password
    from gateway.models.admin_user import AdminUser

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(AdminUser).where(AdminUser.username == settings.SUPERADMIN_USERNAME))
        if result.scalar_one_or_none():
            return
        admin = AdminUser(
            username=settings.SUPERADMIN_USERNAME,
            email=settings.SUPERADMIN_EMAIL,
            hashed_password=hash_password(settings.SUPERADMIN_PASSWORD),
            is_superadmin=True,
        )
        db.add(admin)
        await db.commit()
        logger.info("Superadmin '%s' created.", settings.SUPERADMIN_USERNAME)


async def _seed_cache_config() -> None:
    from gateway.models.cache_config import CacheConfig

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(CacheConfig))
        if result.scalar_one_or_none():
            return
        db.add(CacheConfig())
        await db.commit()
        logger.info("Default cache config row seeded.")


async def _seed_system_config() -> None:
    """Seed the singleton system_config row (id=1) on first boot.

    Uses settings.LOG_PROMPT_CONTENT as the initial value so existing .env
    deployments see no behaviour change. On subsequent boots the DB value wins;
    changing .env after first run has no effect (superadmin must use the UI).
    """
    from gateway.models.system_config import SystemConfig

    async with AsyncSessionLocal() as db:
        existing = await db.get(SystemConfig, 1)
        if existing:
            return
        db.add(SystemConfig(id=1, log_prompt_content=settings.LOG_PROMPT_CONTENT))
        await db.commit()
        logger.info(
            "System config seeded (log_prompt_content=%s).",
            settings.LOG_PROMPT_CONTENT,
        )


async def _seed_default_guardrails() -> None:
    """
    On first run, create a baseline set of guardrails that are always active.
    Skipped entirely if any guardrail row already exists (not a first run).
    """
    from gateway.models.guardrail_config import GuardrailConfig

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(GuardrailConfig))
        if result.scalars().first():
            return  # Guardrails already configured — don't overwrite admin changes

        defaults = [
            GuardrailConfig(
                name="Prompt Injection Shield",
                guardrail_type="prompt_injection",
                applies_to="both",
                config_json={},
                action_on_trigger="rewrite",
                is_active=True,
            ),
            GuardrailConfig(
                name="Harmful Content Filter",
                guardrail_type="content_filter",
                applies_to="both",
                config_json={"categories": ["violence", "self-harm", "adult", "hate"]},
                action_on_trigger="block",
                is_active=True,
            ),
            GuardrailConfig(
                name="PII Redaction",
                guardrail_type="pii_redaction",
                applies_to="both",
                config_json={},
                action_on_trigger="redact",
                is_active=True,
            ),
        ]
        for g in defaults:
            db.add(g)
        await db.commit()
        logger.info("Seeded %d default guardrail(s).", len(defaults))


async def _seed_default_models() -> None:
    """On first run, create sensible default model configs for every provider key that is set."""
    from gateway.models.model_config import ModelConfig

    # (display_name, litellm_model_name, provider, api_key_env_var, condition)
    candidates = [
        ("gpt-4o-mini",          "gpt-4o-mini",                          "openai",    "OPENAI_API_KEY",    bool(settings.OPENAI_API_KEY)),
        ("gpt-4o",               "gpt-4o",                               "openai",    "OPENAI_API_KEY",    bool(settings.OPENAI_API_KEY)),
        ("claude-3-5-haiku",     "anthropic/claude-3-5-haiku-20241022",  "anthropic", "ANTHROPIC_API_KEY", bool(settings.ANTHROPIC_API_KEY)),
        ("claude-3-5-sonnet",    "anthropic/claude-3-5-sonnet-20241022", "anthropic", "ANTHROPIC_API_KEY", bool(settings.ANTHROPIC_API_KEY)),
        ("gemini-1.5-flash",     "gemini/gemini-1.5-flash",              "gemini",    "GEMINI_API_KEY",    bool(settings.GEMINI_API_KEY)),
        ("ollama-llama3",        "ollama/llama3",                        "ollama",    "OLLAMA_API_BASE",   True),  # always available if Ollama is running
    ]

    async with AsyncSessionLocal() as db:
        # Skip entirely if any model already exists (not a first run)
        result = await db.execute(select(ModelConfig))
        if result.scalars().first():
            return

        seeded = []
        for display_name, litellm_name, provider, env_var, condition in candidates:
            if not condition:
                continue
            # Skip Ollama default unless an explicit base URL was set (non-default)
            if provider == "ollama" and settings.OLLAMA_API_BASE == "http://localhost:11434":
                continue
            db.add(ModelConfig(
                display_name=display_name,
                litellm_model_name=litellm_name,
                provider=provider,
                api_key_env_var=env_var,
                is_active=True,
                status="active",
            ))
            seeded.append(display_name)

        if seeded:
            await db.commit()
            logger.info("Seeded %d default model config(s): %s", len(seeded), seeded)
        else:
            logger.warning(
                "No provider API keys found in .env — no default models seeded. "
                "Set OPENAI_API_KEY, ANTHROPIC_API_KEY, or GEMINI_API_KEY, then restart."
            )


async def _init_litellm(app: FastAPI) -> None:
    from gateway.models.model_config import ModelConfig

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(ModelConfig).where(ModelConfig.is_active == True))
        model_configs = result.scalars().all()

    svc = LiteLLMService()
    svc.initialize(model_configs)
    svc.register_callbacks([BudgetEnforcementCallback(), RequestLoggingCallback()])
    app.state.litellm_service = svc
    logger.info("LiteLLM service ready.")


async def _init_cache() -> None:
    from gateway.models.cache_config import CacheConfig

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(CacheConfig))
        config = result.scalar_one_or_none()
    apply_cache_config(config)


async def _scheduled_budget_reset() -> None:
    """Reset virtual key spend counters — runs 1st of each month at 00:05 UTC."""
    from sqlalchemy import update
    from gateway.models.virtual_key import VirtualKey
    from datetime import datetime, timezone

    logger.info("APScheduler: running monthly budget reset…")
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(VirtualKey).values(
                current_spend_usd=0.0,
                budget_reset_at=datetime.now(timezone.utc),
            )
        )
        await db.commit()
    logger.info("APScheduler: monthly budget reset complete.")


async def _scheduled_blocklist_cleanup() -> None:
    """Remove expired refresh token blocklist entries — runs daily at 03:00 UTC."""
    from sqlalchemy import delete
    from gateway.models.admin_user import RefreshTokenBlocklist
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    logger.info("APScheduler: cleaning up expired blocklist tokens…")
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            delete(RefreshTokenBlocklist).where(RefreshTokenBlocklist.expires_at < now)
        )
        await db.commit()
    logger.info("APScheduler: removed %d expired blocklist entries.", result.rowcount)


async def _scheduled_alert_evaluation() -> None:
    """Evaluate alert rules — runs every 5 minutes."""
    try:
        from gateway.services.alert_service import AlertService
        async with AsyncSessionLocal() as db:
            svc = AlertService(db)
            await svc.evaluate_all_rules()
            await db.commit()
    except Exception as exc:
        logger.warning("APScheduler: alert evaluation failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────────
    logger.info("Starting PromptCaliper Gateway v%s …", settings.APP_VERSION)
    await _create_tables()
    await _seed_superadmin()
    await _seed_cache_config()
    await _seed_system_config()
    await _seed_default_models()
    await _seed_default_guardrails()
    await _init_litellm(app)
    await _init_cache()

    # ── APScheduler ──────────────────────────────────────────────────────────
    scheduler = AsyncIOScheduler(timezone="UTC")
    # Monthly budget reset: 1st of every month at 00:05 UTC
    scheduler.add_job(
        _scheduled_budget_reset,
        CronTrigger(day=1, hour=0, minute=5),
        id="monthly_budget_reset",
        replace_existing=True,
    )
    # Alert evaluation: every 5 minutes
    scheduler.add_job(
        _scheduled_alert_evaluation,
        CronTrigger(minute="*/5"),
        id="alert_evaluation",
        replace_existing=True,
    )
    # Blocklist cleanup: daily at 03:00 UTC
    scheduler.add_job(
        _scheduled_blocklist_cleanup,
        CronTrigger(hour=3, minute=0),
        id="blocklist_cleanup",
        replace_existing=True,
    )
    scheduler.start()
    app.state.scheduler = scheduler
    logger.info("Gateway ready on port %d. Scheduler started.", settings.GATEWAY_PORT)

    yield  # App is running

    # ── Shutdown ─────────────────────────────────────────────────────────────
    logger.info("Shutting down gateway…")
    scheduler.shutdown(wait=False)
    await engine.dispose()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add defensive HTTP security headers to every response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = "no-store"
        # Only set HSTS when running over TLS (not local HTTP dev)
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


def create_app() -> FastAPI:
    app = FastAPI(
        title="PromptCaliper AI Gateway",
        version=settings.APP_VERSION,
        description="Internal AI gateway with LiteLLM routing, budget control, and observability.",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    # ── Security headers ─────────────────────────────────────────────────────
    app.add_middleware(SecurityHeadersMiddleware)

    # ── CORS ─────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key"],
    )

    # ── Global error handler ──────────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        detail = f"{type(exc).__name__}: {exc}" if settings.DEBUG else "Internal server error"
        return JSONResponse(
            status_code=500,
            content={"detail": detail},
        )

    # ── Routers ──────────────────────────────────────────────────────────────
    app.include_router(auth_router,    prefix="/api/auth",    tags=["auth"])
    app.include_router(gateway_router, prefix="/api/v1",      tags=["completion"])

    # Management routers (added in Phase 2 & 3)
    _register_management_routers(app)

    @app.get("/api/health", tags=["health"])
    async def health():
        """Liveness + readiness probe: verifies database connectivity."""
        db_ok = False
        db_error: str | None = None
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(text("SELECT 1"))
            db_ok = True
        except Exception as exc:
            db_error = str(exc)
            logger.error("Health check: database unreachable — %s", exc)

        payload = {
            "status": "ok" if db_ok else "degraded",
            "version": settings.APP_VERSION,
            "database": "ok" if db_ok else f"error: {db_error}",
        }
        status_code = 200 if db_ok else 503
        return JSONResponse(content=payload, status_code=status_code)

    return app


def _register_management_routers(app: FastAPI) -> None:
    """Register management API routers.

    ImportError is logged at ERROR level so misconfigured or broken routers
    are immediately visible in startup logs rather than silently disappearing.
    """
    _routers = [
        ("gateway.routers.virtual_keys", "router", "/api/virtual-keys", ["virtual-keys"]),
        ("gateway.routers.teams",         "router", "/api/teams",         ["teams"]),
        ("gateway.routers.users",         "router", "/api/users",         ["users"]),
        ("gateway.routers.models",        "router", "/api/models",        ["models"]),
        ("gateway.routers.budgets",       "router", "/api/budgets",       ["budgets"]),
        ("gateway.routers.rate_limits",   "router", "/api/rate-limits",   ["rate-limits"]),
        ("gateway.routers.logs",          "router", "/api/logs",          ["logs"]),
        ("gateway.routers.analytics",     "router", "/api/analytics",     ["analytics"]),
        ("gateway.routers.guardrails",    "router", "/api/guardrails",    ["guardrails"]),
        ("gateway.routers.cache",         "router", "/api/cache",         ["cache"]),
        ("gateway.routers.alerts",        "router", "/api/alerts",        ["alerts"]),
    ]
    for module_path, attr, prefix, tags in _routers:
        try:
            import importlib
            module = importlib.import_module(module_path)
            router_obj = getattr(module, attr)
            app.include_router(router_obj, prefix=prefix, tags=tags)
        except ImportError as exc:
            logger.error(
                "Failed to load router '%s' (prefix=%s): %s — this API surface will be unavailable.",
                module_path, prefix, exc,
            )


app = create_app()
