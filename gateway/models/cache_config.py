from datetime import datetime
from decimal import Decimal
from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from gateway.db.base import Base


class CacheConfig(Base):
    """Singleton — only one row ever exists."""
    __tablename__ = "cache_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    cache_type: Mapped[str] = mapped_column(String(30), default="in-memory")  # in-memory|redis|semantic
    redis_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    semantic_similarity_threshold: Mapped[Decimal] = mapped_column(Numeric(4, 3), default=Decimal("0.950"))
    ttl_seconds: Mapped[int] = mapped_column(Integer, default=3600)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
