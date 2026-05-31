"""
LiteLLM SDK integration hub.

Uses litellm.Router for model routing, load balancing, and fallbacks.
Callbacks are registered at startup and handle logging + budget enforcement.
"""
import logging
import os
from typing import Any

import litellm
from litellm import Router

from gateway.config import settings
from gateway.firestore_store import FirestoreStore, store

logger = logging.getLogger(__name__)

# Suppress noisy LiteLLM success prints in non-debug mode
litellm.suppress_debug_info = not settings.DEBUG
litellm.set_verbose = settings.DEBUG


def active_model_configs(db: FirestoreStore | None = None) -> list:
    """Return active model configs from Firestore (list+filter avoids brittle bool queries)."""
    db = db or store
    return [m for m in db.list("model_configs") if getattr(m, "is_active", False)]


def normalize_vertex_litellm_model(litellm_model_name: str) -> str:
    """Normalize legacy vertex_ai/global/<model> paths to vertex_ai/<model>."""
    prefix = "vertex_ai/global/"
    if litellm_model_name.startswith(prefix):
        return f"vertex_ai/{litellm_model_name[len(prefix):]}"
    return litellm_model_name


def vertex_litellm_params(mc) -> dict[str, Any]:
    """Build LiteLLM params for Vertex AI models with global region."""
    params: dict[str, Any] = {
        "model": normalize_vertex_litellm_model(mc.litellm_model_name),
        "weight": mc.routing_weight,
        "vertex_location": settings.VERTEXAI_LOCATION or "global",
    }
    if settings.VERTEXAI_PROJECT:
        params["vertex_project"] = settings.VERTEXAI_PROJECT
    return params


class LiteLLMService:
    def __init__(self):
        self.router: Router | None = None
        self._model_configs: list = []

    def initialize(self, model_configs: list) -> None:
        """Build the LiteLLM Router from DB model configs. Called at startup and on config change."""
        self._model_configs = model_configs

        # Inject provider API keys into environment so LiteLLM can pick them up
        self._sync_env_keys()

        model_list = []
        fallback_map: dict[str, list] = {}

        for mc in model_configs:
            if not mc.is_active:
                continue

            if mc.provider == "vertex_ai" or str(mc.litellm_model_name).startswith("vertex_ai/"):
                litellm_params = vertex_litellm_params(mc)
            else:
                litellm_params = {
                    "model": mc.litellm_model_name,
                    "weight": mc.routing_weight,
                }
                if mc.api_key_env_var and os.environ.get(mc.api_key_env_var):
                    litellm_params["api_key"] = os.environ[mc.api_key_env_var]

            entry = {
                "model_name": mc.display_name,
                "litellm_params": litellm_params,
            }
            if mc.api_base:
                entry["litellm_params"]["api_base"] = mc.api_base
            if (
                mc.provider != "vertex_ai"
                and mc.api_key_env_var
                and os.environ.get(mc.api_key_env_var)
            ):
                entry["litellm_params"]["api_key"] = os.environ[mc.api_key_env_var]

            model_list.append(entry)

            # Build fallback list: group by display_name, ordered by fallback_priority
            if mc.fallback_priority is not None:
                fallback_map.setdefault(mc.display_name, []).append(
                    (mc.fallback_priority, mc.litellm_model_name)
                )

        if not model_list:
            logger.warning("No active model configs found — LiteLLM Router started with no models.")
            self.router = None
            return

        # Build fallbacks in priority order
        fallbacks = []
        for display_name, priority_pairs in fallback_map.items():
            sorted_models = [m for _, m in sorted(priority_pairs)]
            if len(sorted_models) > 1:
                fallbacks.append({display_name: sorted_models[1:]})

        try:
            self.router = Router(
                model_list=model_list,
                routing_strategy=settings.LITELLM_ROUTING_STRATEGY,
                fallbacks=fallbacks if fallbacks else None,
                num_retries=settings.LITELLM_NUM_RETRIES,
                timeout=settings.LITELLM_TIMEOUT,
                retry_after=5,
            )
            logger.info("LiteLLM Router initialized with %d model(s).", len(model_list))
        except Exception as exc:
            logger.error("Failed to initialize LiteLLM Router: %s", exc)
            self.router = None

    def register_callbacks(self, callbacks: list) -> None:
        """Register LiteLLM callbacks (logging, budget enforcement)."""
        litellm.callbacks = callbacks
        logger.info("Registered %d LiteLLM callback(s).", len(callbacks))

    def ensure_router(self, db: FirestoreStore | None = None) -> bool:
        """Load the router from Firestore when empty (e.g. models added after startup)."""
        if self.router is not None:
            return True
        configs = active_model_configs(db)
        if not configs:
            return False
        self.initialize(configs)
        return self.router is not None

    async def complete(
        self,
        messages: list[dict],
        model: str,
        virtual_key_id: int | None = None,
        team_id: int | None = None,
        extra_metadata: dict | None = None,
        **kwargs: Any,
    ) -> Any:
        """Route a chat completion through LiteLLM Router."""
        if not self.ensure_router():
            raise RuntimeError(
                "LiteLLM Router not initialized. Add at least one active model via "
                "POST /api/models or the Models tab in the UI."
            )

        metadata = {
            "virtual_key_id": virtual_key_id,
            "team_id": team_id,
            **(extra_metadata or {}),
        }

        # Prepend safety system prompt if configured and not already present.
        # This anchors the model's behaviour before any user-supplied messages
        # and resists prompt-injection attempts that try to override instructions.
        if settings.SAFETY_SYSTEM_PROMPT:
            has_system = any(m.get("role") == "system" for m in messages)
            if not has_system:
                messages = [{"role": "system", "content": settings.SAFETY_SYSTEM_PROMPT}] + list(messages)
            else:
                # Prepend to the existing system message so it takes precedence
                patched = []
                prepended = False
                for m in messages:
                    if m.get("role") == "system" and not prepended:
                        patched.append({
                            **m,
                            "content": settings.SAFETY_SYSTEM_PROMPT + "\n\n" + (m.get("content") or ""),
                        })
                        prepended = True
                    else:
                        patched.append(m)
                messages = patched

        # Enable caching on this call if a cache backend is configured globally
        if litellm.cache is not None:
            kwargs.setdefault("caching", True)

        response = await self.router.acompletion(
            model=model,
            messages=messages,
            metadata=metadata,
            **kwargs,
        )
        return response

    def reinitialize(self, model_configs: list) -> None:
        """Rebuild router after model config changes. Thread-safe by Python GIL."""
        logger.info("Re-initializing LiteLLM Router after config change.")
        self.initialize(model_configs)

    def _sync_env_keys(self) -> None:
        """Push provider API keys from settings into os.environ so LiteLLM picks them up."""
        key_map = {
            "OPENAI_API_KEY": settings.OPENAI_API_KEY,
            "ANTHROPIC_API_KEY": settings.ANTHROPIC_API_KEY,
            "AZURE_API_KEY": settings.AZURE_API_KEY,
            "AZURE_API_BASE": settings.AZURE_API_BASE,
            "AZURE_API_VERSION": settings.AZURE_API_VERSION,
            "GEMINI_API_KEY": settings.GEMINI_API_KEY,
            "AWS_ACCESS_KEY_ID": settings.AWS_ACCESS_KEY_ID,
            "AWS_SECRET_ACCESS_KEY": settings.AWS_SECRET_ACCESS_KEY,
            "AWS_REGION_NAME": settings.AWS_REGION_NAME,
            "VERTEXAI_PROJECT": settings.VERTEXAI_PROJECT,
            "VERTEXAI_LOCATION": settings.VERTEXAI_LOCATION,
        }
        for k, v in key_map.items():
            if v:
                os.environ[k] = v
        if settings.VERTEXAI_PROJECT:
            os.environ.setdefault("GOOGLE_CLOUD_PROJECT", settings.VERTEXAI_PROJECT)
        location = settings.VERTEXAI_LOCATION or "global"
        litellm.vertex_location = location
        if settings.VERTEXAI_PROJECT:
            litellm.vertex_project = settings.VERTEXAI_PROJECT
