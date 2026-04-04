"""
SystemConfig — singleton runtime configuration table (always id=1).

WHY THIS EXISTS
---------------
LOG_PROMPT_CONTENT was previously a static Pydantic setting read from .env at
process startup. That meant changing it required an .env edit + server restart,
making it impractical to toggle during a live debug or compliance audit session.

This model moves the flag into the database so a superadmin can flip it through
the UI at runtime without any downtime. The .env value is still respected as the
initial seed on first boot, preserving backwards compatibility.

DESIGN DECISIONS
----------------
1. Single-row singleton (id=1) — same pattern as CacheConfig in this codebase.
   Only one row ever exists; all workers read from the same DB record.

2. In-process TTL cache (_CACHE_TTL_SECONDS = 10) — the logging callback fires
   on every LLM request. Without a cache we would issue a SELECT on every call.
   With a 10-second TTL the hot path is a pure memory read; workers converge to
   a new toggle value within 10 s of a PATCH without any inter-process signalling
   or Redis dependency.

3. invalidate_log_prompt_content_cache() — called by the PATCH endpoint in the
   same worker process immediately after the DB write, so that worker reflects
   the change instantly rather than waiting for the TTL to expire.

MULTI-WORKER NOTE
-----------------
In production (2+ uvicorn workers) each process has its own cache. The worker
that handles the PATCH invalidates its cache immediately; other workers see the
change within _CACHE_TTL_SECONDS. For a rarely-changed debug/privacy flag this
is acceptable. If sub-second consistency is ever required, replace the TTL cache
with a Redis-backed pub/sub invalidation.
"""

import time

from sqlalchemy import Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.db.base import Base


class SystemConfig(Base):
    """Singleton runtime config row — only id=1 ever exists.

    Stores superadmin-controlled flags that must survive process restarts
    (stored in DB) but must also be readable on the hot LLM-request path
    without a DB round-trip (served from TTL cache).
    """

    __tablename__ = "system_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # When True, full prompt messages and LLM response content are written to
    # the request_logs table on every call. Keep False in production unless
    # actively debugging — enabling this stores potentially sensitive user
    # content in the database.
    log_prompt_content: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )


# ---------------------------------------------------------------------------
# In-process TTL cache
# ---------------------------------------------------------------------------
# Module-level mutable state shared across all coroutines within one worker
# process. Python's GIL makes bool assignment atomic, so no lock is needed.

_cached_value: bool | None = None  # None means "not yet loaded"
_cache_expiry: float = 0.0         # monotonic timestamp after which cache is stale
_CACHE_TTL_SECONDS: float = 10.0   # re-query DB at most once every 10 s per worker


async def get_log_prompt_content(db: AsyncSession) -> bool:
    """Return the current log_prompt_content flag using an in-process TTL cache.

    Callers on the hot path (e.g. the logging callback) should pass in their
    already-open AsyncSession to avoid opening an extra DB connection.

    Cache behaviour:
    - Hit  (within TTL): returns cached bool — no DB I/O.
    - Miss (expired/first call): issues a single SELECT by primary key,
      updates the cache, returns the value.
    """
    global _cached_value, _cache_expiry

    now = time.monotonic()
    if _cached_value is not None and now < _cache_expiry:
        return _cached_value

    config = await db.get(SystemConfig, 1)
    value = config.log_prompt_content if config else False
    _cached_value = value
    _cache_expiry = now + _CACHE_TTL_SECONDS
    return value


def invalidate_log_prompt_content_cache() -> None:
    """Force the next get_log_prompt_content() call to re-query the DB.

    Called immediately after the PATCH endpoint writes a new value so the
    current worker process reflects the change without waiting for the TTL.
    Other worker processes will pick up the change within _CACHE_TTL_SECONDS.
    """
    global _cache_expiry
    _cache_expiry = 0.0
