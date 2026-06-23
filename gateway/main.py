"""PromptCaliper AI Gateway — FastAPI application factory."""
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from gateway.auth.router import router as auth_router
from gateway.callbacks.budget_callback import BudgetEnforcementCallback
from gateway.callbacks.logging_callback import RequestLoggingCallback
from gateway.config import settings
from gateway.firestore_store import store, utcnow
from gateway.routers.gateway import router as gateway_router
from gateway.services.cache_service import apply_cache_config
from gateway.services.litellm_service import LiteLLMService, active_model_configs

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def _create_tables() -> None:
    logger.info("Firestore database '%s' ready.", settings.FIRESTORE_DATABASE)


async def _seed_superadmin() -> None:
    from gateway.auth.service import hash_password

    existing = store.first("admin_users", username=settings.SUPERADMIN_USERNAME)
    if existing:
        existing.hashed_password = hash_password(settings.SUPERADMIN_PASSWORD)
        existing.is_active = True
        existing.is_superadmin = True
        store.save(existing)
        logger.info("Superadmin '%s' password synced from env.", settings.SUPERADMIN_USERNAME)
        return
    store.create("admin_users", {
        "username": settings.SUPERADMIN_USERNAME,
        "email": settings.SUPERADMIN_EMAIL,
        "hashed_password": hash_password(settings.SUPERADMIN_PASSWORD),
        "is_superadmin": True,
        "is_active": True,
        "last_login_at": None,
    })
    logger.info("Superadmin '%s' created.", settings.SUPERADMIN_USERNAME)


async def _seed_vertex_models() -> None:
    """Seed default Vertex AI Gemini models when VERTEXAI_PROJECT is configured."""
    if not settings.VERTEXAI_PROJECT:
        return

    # Vertex AI image generation family commonly referred to as "nano banana".
    defaults = [
        ("gemini-3.1-pro", "vertex_ai/gemini-3.1-pro"),
        ("gemini-3.5-flash", "vertex_ai/gemini-3.5-flash"),
        ("gemini-2.5-flash-image", "vertex_ai/gemini-2.5-flash-image"),
        ("gemini-3.1-flash-image", "vertex_ai/gemini-3.1-flash-image"),
        ("gemini-3-pro-image-preview", "vertex_ai/gemini-3-pro-image-preview"),
        ("veo-3.1", "vertex_ai/veo-3.1-generate-001"),
        ("veo-3.1-fast", "vertex_ai/veo-3.1-fast-generate-001"),
        ("veo-3.1-lite", "vertex_ai/veo-3.1-lite-generate-001"),
        ("veo-3.0", "vertex_ai/veo-3.0-generate-001"),
        ("veo-3.0-fast", "vertex_ai/veo-3.0-fast-generate-001"),
        ("veo-2.0", "vertex_ai/veo-2.0-generate-001"),
    ]
    seeded = []
    for display_name, litellm_name in defaults:
        existing = store.first("model_configs", display_name=display_name)
        if existing:
            if existing.litellm_model_name != litellm_name:
                existing.litellm_model_name = litellm_name
                store.save(existing)
                logger.info("Updated model config for '%s' to '%s'", display_name, litellm_name)
            continue
        store.create("model_configs", {
            "display_name": display_name,
            "litellm_model_name": litellm_name,
            "provider": "vertex_ai",
            "api_base": None,
            "api_key_env_var": None,
            "routing_weight": 1,
            "fallback_priority": None,
            "max_tokens": None,
            "temperature_default": None,
            "cost_per_input_token": None,
            "cost_per_output_token": None,
            "context_window": None,
            "avg_latency_ms": None,
            "is_active": True,
            "status": "active",
        })
        seeded.append(display_name)
    if seeded:
        logger.info("Seeded Vertex AI model(s): %s", seeded)


async def _init_litellm(app: FastAPI) -> None:
    model_configs = active_model_configs(store)

    svc = LiteLLMService()
    svc.initialize(model_configs)
    svc.register_callbacks([BudgetEnforcementCallback(), RequestLoggingCallback()])
    app.state.litellm_service = svc
    logger.info("LiteLLM service ready.")


async def _init_cache() -> None:
    configs = store.list("cache_configs")
    config = configs[0] if configs else None
    apply_cache_config(config)


async def _scheduled_budget_reset() -> None:
    """Reset virtual key spend counters — runs 1st of each month at 00:05 UTC."""

    logger.info("APScheduler: running monthly budget reset…")
    for key in store.list("virtual_keys"):
        key.current_spend_usd = 0.0
        key.budget_reset_at = utcnow()
        store.save(key)
    logger.info("APScheduler: monthly budget reset complete.")


async def _scheduled_blocklist_cleanup() -> None:
    """Remove expired refresh token blocklist entries — runs daily at 03:00 UTC."""
    now = utcnow()
    logger.info("APScheduler: cleaning up expired blocklist tokens…")
    removed = 0
    for token in store.list("refresh_token_blocklist"):
        if token.expires_at < now:
            store.delete("refresh_token_blocklist", token.id)
            removed += 1
    logger.info("APScheduler: removed %d expired blocklist entries.", removed)


async def _scheduled_alert_evaluation() -> None:
    """Evaluate alert rules — runs every 5 minutes."""
    try:
        from gateway.services.alert_service import AlertService
        svc = AlertService(store)
        await svc.evaluate_all_rules()
    except Exception as exc:
        logger.warning("APScheduler: alert evaluation failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────────
    logger.info("Starting PromptCaliper Gateway v%s …", settings.APP_VERSION)
    await _create_tables()
    await _seed_superadmin()
    await _seed_vertex_models()
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
    return


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add defensive HTTP security headers to every response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if request.url.path.startswith("/assets/") or request.url.path == "/favicon.ico":
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
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
            store.list("system_config")
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

    _register_frontend_routes(app)

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


def _register_frontend_routes(app: FastAPI) -> None:
    """Serve the built SPA from the same container when enabled."""
    if not settings.SERVE_FRONTEND:
        return

    frontend_root = Path(settings.FRONTEND_DIST_DIR).expanduser().resolve()
    index_file = frontend_root / "index.html"
    assets_dir = frontend_root / "assets"

    if not index_file.exists():
        logger.warning(
            "SERVE_FRONTEND is enabled, but no built frontend was found at %s.",
            index_file,
        )
        return

    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="frontend-assets")

    @app.get("/", include_in_schema=False)
    async def frontend_index():
        return FileResponse(index_file)

    @app.get("/{path:path}", include_in_schema=False)
    async def frontend_spa(path: str):
        if path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})

        candidate = (frontend_root / path).resolve()
        if (candidate == frontend_root or frontend_root in candidate.parents) and candidate.is_file():
            return FileResponse(candidate)

        return FileResponse(index_file)


app = create_app()
