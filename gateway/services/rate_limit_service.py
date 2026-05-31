"""
In-process rate limiting (dev) with Redis fallback (prod).
Tracks RPM and TPM per virtual key using sliding 60-second windows.
"""
import logging
import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException

logger = logging.getLogger(__name__)

# In-memory store: { "rpm:{key_id}:{minute_bucket}" -> count }
_counters: dict[str, int] = defaultdict(int)
_expiry: dict[str, float] = {}
_lock = Lock()


def _bucket(key: str) -> str:
    return f"{key}:{int(time.time() // 60)}"


def _cleanup() -> None:
    now = time.time()
    expired = [k for k, exp in _expiry.items() if exp < now]
    for k in expired:
        _counters.pop(k, None)
        _expiry.pop(k, None)


def check_and_increment_memory(key_id: int, rpm_limit: int | None, tpm_limit: int | None, token_count: int = 0) -> None:
    with _lock:
        _cleanup()

        if rpm_limit:
            rpm_key = _bucket(f"rpm:{key_id}")
            _counters[rpm_key] += 1
            _expiry[rpm_key] = time.time() + 120
            if _counters[rpm_key] > rpm_limit:
                raise HTTPException(status_code=429, detail=f"Rate limit exceeded: {rpm_limit} RPM")

        if tpm_limit and token_count > 0:
            tpm_key = _bucket(f"tpm:{key_id}")
            _counters[tpm_key] += token_count
            _expiry[tpm_key] = time.time() + 120
            if _counters[tpm_key] > tpm_limit:
                raise HTTPException(status_code=429, detail=f"Rate limit exceeded: {tpm_limit} TPM")


async def check_and_increment_redis(
    redis_client,
    key_id: int,
    rpm_limit: int | None,
    tpm_limit: int | None,
    token_count: int = 0,
) -> None:
    minute_bucket = int(time.time() // 60)

    if rpm_limit:
        rpm_key = f"rpm:{key_id}:{minute_bucket}"
        current = await redis_client.incr(rpm_key)
        await redis_client.expire(rpm_key, 120)
        if current > rpm_limit:
            raise HTTPException(status_code=429, detail=f"Rate limit exceeded: {rpm_limit} RPM")

    if tpm_limit and token_count > 0:
        tpm_key = f"tpm:{key_id}:{minute_bucket}"
        # Use a pipeline so the read-increment-expire is atomic
        pipe = redis_client.pipeline()
        pipe.incrby(tpm_key, token_count)
        pipe.expire(tpm_key, 120)
        results = await pipe.execute()
        new_total = results[0]
        if new_total > tpm_limit:
            raise HTTPException(status_code=429, detail=f"Rate limit exceeded: {tpm_limit} TPM")


def get_current_usage_memory(key_id: int) -> dict:
    with _lock:
        minute_bucket = int(time.time() // 60)
        rpm = _counters.get(f"rpm:{key_id}:{minute_bucket}", 0)
        tpm = _counters.get(f"tpm:{key_id}:{minute_bucket}", 0)
    return {"rpm": rpm, "tpm": tpm}
