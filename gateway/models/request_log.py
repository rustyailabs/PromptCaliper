from datetime import datetime
from decimal import Decimal
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from gateway.db.base import Base


class RequestLog(Base):
    __tablename__ = "request_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    request_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    virtual_key_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("virtual_keys.id"), nullable=True, index=True)
    team_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("teams.id"), nullable=True, index=True)
    model_config_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("model_configs.id"), nullable=True, index=True)
    litellm_model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    requested_model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    prompt_messages: Mapped[list] = mapped_column(JSON, nullable=False)
    response_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=Decimal("0.0"))
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    guardrail_triggered: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
