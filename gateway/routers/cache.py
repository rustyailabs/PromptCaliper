import litellm
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.db.session import get_db
from gateway.dependencies import get_current_user
from gateway.models.cache_config import CacheConfig
from gateway.models.request_log import RequestLog
from gateway.services.cache_service import apply_cache_config

router = APIRouter(dependencies=[Depends(get_current_user)])


class CacheConfigUpdate(BaseModel):
    cache_type: str | None = None  # in-memory|redis|semantic
    redis_url: str | None = None
    semantic_similarity_threshold: float | None = None
    ttl_seconds: int | None = None
    is_enabled: bool | None = None


class CacheConfigResponse(BaseModel):
    id: int
    cache_type: str
    redis_url: str | None
    semantic_similarity_threshold: float
    ttl_seconds: int
    is_enabled: bool

    model_config = {"from_attributes": True}


@router.get("/config", response_model=CacheConfigResponse)
async def get_config(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CacheConfig))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Cache config not found")
    return config


@router.put("/config", response_model=CacheConfigResponse)
async def update_config(body: CacheConfigUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CacheConfig))
    config = result.scalar_one_or_none()
    if not config:
        config = CacheConfig()
        db.add(config)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(config, field, value)
    await db.flush()
    apply_cache_config(config)  # Apply immediately
    await db.refresh(config)
    return config


@router.get("/stats")
async def cache_stats(db: AsyncSession = Depends(get_db)):
    cache = litellm.cache

    # Entry count from in-memory cache object
    cache_obj = getattr(cache, "cache", None)
    entry_count = 0
    if cache_obj and hasattr(cache_obj, "cache_dict"):
        entry_count = len(cache_obj.cache_dict)

    # Hits and misses from request_logs (persisted, survives restarts)
    hits_result = await db.execute(
        select(func.count(RequestLog.id)).where(
            RequestLog.status_code == 200,
            RequestLog.cache_hit == True,
        )
    )
    total_hits = int(hits_result.scalar() or 0)

    total_result = await db.execute(
        select(func.count(RequestLog.id)).where(RequestLog.status_code == 200)
    )
    total = int(total_result.scalar() or 0)

    savings_result = await db.execute(
        select(func.coalesce(func.sum(RequestLog.cost_usd), 0)).where(
            RequestLog.cache_hit == True
        )
    )
    estimated_savings = float(savings_result.scalar() or 0)

    total_misses = max(total - total_hits, 0)
    hit_rate = round(total_hits / total * 100, 1) if total else 0

    return {
        "enabled": cache is not None,
        "cache_type": getattr(cache, "type", "none") if cache else "none",
        "entry_count": entry_count,
        "total_hits": total_hits,
        "total_misses": total_misses,
        "hit_rate_pct": hit_rate,
        "estimated_savings_usd": estimated_savings,
    }


@router.delete("/clear")
async def clear_cache():
    cache = litellm.cache
    if not cache:
        return {"cleared_entries": 0}
    cache_obj = getattr(cache, "cache", None)
    cleared = 0
    if cache_obj and hasattr(cache_obj, "cache_dict"):
        cleared = len(cache_obj.cache_dict)
        cache_obj.cache_dict.clear()
    return {"cleared_entries": cleared}
