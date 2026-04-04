"""Apply/update LiteLLM caching configuration from DB settings."""
import logging

import litellm
from litellm.caching.caching import Cache

from gateway.models.cache_config import CacheConfig

logger = logging.getLogger(__name__)


def apply_cache_config(config: CacheConfig | None) -> None:
    if not config or not config.is_enabled:
        litellm.cache = None
        logger.info("LiteLLM cache disabled.")
        return

    try:
        if config.cache_type == "redis":
            from urllib.parse import urlparse
            parsed = urlparse(config.redis_url or "redis://localhost:6379/0")
            litellm.cache = Cache(
                type="redis",
                host=parsed.hostname or "localhost",
                port=parsed.port or 6379,
                password=parsed.password,
                ttl=config.ttl_seconds,
            )
            logger.info("LiteLLM Redis cache enabled.")

        elif config.cache_type in ("semantic", "redis-semantic"):
            from urllib.parse import urlparse
            parsed = urlparse(config.redis_url or "redis://localhost:6379/0")
            litellm.cache = Cache(
                type="redis-semantic",
                host=parsed.hostname or "localhost",
                port=parsed.port or 6379,
                password=parsed.password,
                similarity_threshold=float(config.semantic_similarity_threshold or 0.95),
                ttl=config.ttl_seconds,
            )
            logger.info("LiteLLM semantic cache enabled (threshold=%.3f).", float(config.semantic_similarity_threshold))

        else:  # in-memory
            litellm.cache = Cache(type="local", ttl=config.ttl_seconds)
            logger.info("LiteLLM in-memory cache enabled.")

    except Exception as exc:
        logger.error("Failed to apply cache config: %s", exc)
        litellm.cache = None
