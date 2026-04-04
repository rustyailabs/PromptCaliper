from datetime import datetime
from decimal import Decimal
from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from gateway.db.base import Base


class ModelConfig(Base):
    __tablename__ = "model_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    litellm_model_name: Mapped[str] = mapped_column(String(200), nullable=False)  # e.g. "azure/gpt-4-turbo"
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # openai|anthropic|azure|gemini|bedrock|ollama
    api_base: Mapped[str | None] = mapped_column(String(500), nullable=True)  # for Azure/Ollama
    api_key_env_var: Mapped[str | None] = mapped_column(String(100), nullable=True)  # env var name holding the key; None for local/keyless models
    routing_weight: Mapped[int] = mapped_column(Integer, default=1)  # higher = more traffic
    fallback_priority: Mapped[int | None] = mapped_column(Integer, nullable=True)  # lower = tried first
    max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    temperature_default: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    cost_per_input_token: Mapped[Decimal | None] = mapped_column(Numeric(10, 8), nullable=True)
    cost_per_output_token: Mapped[Decimal | None] = mapped_column(Numeric(10, 8), nullable=True)
    context_window: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | maintenance | disabled
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
