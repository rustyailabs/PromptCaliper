import litellm
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from gateway.db.session import get_db
from gateway.dependencies import get_current_user
from gateway.firestore_store import FirestoreStore
from gateway.services.cache_service import apply_cache_config

router = APIRouter(dependencies=[Depends(get_current_user)])


class CacheConfigUpdate(BaseModel):
    cache_type: str | None = None
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
def get_config(db: FirestoreStore = Depends(get_db)):
    configs = db.list("cache_configs")
    if not configs:
        raise HTTPException(status_code=404, detail="Cache config not found")
    return configs[0]


@router.put("/config", response_model=CacheConfigResponse)
async def update_config(body: CacheConfigUpdate, db: FirestoreStore = Depends(get_db)):
    configs = db.list("cache_configs")
    config = configs[0] if configs else db.create("cache_configs", {
        "cache_type": "in-memory",
        "redis_url": None,
        "semantic_similarity_threshold": 0.95,
        "ttl_seconds": 3600,
        "is_enabled": False,
    }, doc_id=1)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(config, field, value)
    config = db.save(config)
    apply_cache_config(config)
    return config


@router.get("/stats")
async def cache_stats(db: FirestoreStore = Depends(get_db)):
    cache = litellm.cache
    cache_obj = getattr(cache, "cache", None)
    entry_count = len(cache_obj.cache_dict) if cache_obj and hasattr(cache_obj, "cache_dict") else 0
    logs = [l for l in db.list("request_logs") if l.status_code == 200]
    total_hits = len([l for l in logs if l.cache_hit])
    total = len(logs)
    estimated_savings = sum(float(l.cost_usd or 0) for l in logs if l.cache_hit)
    return {
        "enabled": cache is not None,
        "cache_type": getattr(cache, "type", "none") if cache else "none",
        "entry_count": entry_count,
        "total_hits": total_hits,
        "total_misses": max(total - total_hits, 0),
        "hit_rate_pct": round(total_hits / total * 100, 1) if total else 0,
        "estimated_savings_usd": estimated_savings,
    }


@router.delete("/clear")
async def clear_cache():
    cache = litellm.cache
    cache_obj = getattr(cache, "cache", None)
    if not cache_obj or not hasattr(cache_obj, "cache_dict"):
        return {"cleared_entries": 0}
    cleared = len(cache_obj.cache_dict)
    cache_obj.cache_dict.clear()
    return {"cleared_entries": cleared}
