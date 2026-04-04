from datetime import datetime
from sqlalchemy import Boolean, DateTime, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from gateway.db.base import Base


class GuardrailConfig(Base):
    __tablename__ = "guardrail_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    guardrail_type: Mapped[str] = mapped_column(String(50), nullable=False)  # pii_redaction|content_filter|keyword_block|regex_filter
    applies_to: Mapped[str] = mapped_column(String(20), default="both")  # input|output|both
    config_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    action_on_trigger: Mapped[str] = mapped_column(String(20), default="block")  # block|redact|flag
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
