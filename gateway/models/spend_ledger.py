from datetime import datetime
from decimal import Decimal
from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from gateway.db.base import Base


class SpendLedger(Base):
    """Append-only spend record. Never updated — authoritative source for analytics."""
    __tablename__ = "spend_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    request_log_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("request_logs.id"), nullable=True)
    virtual_key_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("virtual_keys.id"), nullable=True)
    team_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("teams.id"), nullable=True)
    model_config_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("model_configs.id"), nullable=True)
    amount_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    period_month: Mapped[str] = mapped_column(String(7), nullable=False)  # "YYYY-MM"
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_spend_ledger_period_team", "period_month", "team_id"),
        Index("ix_spend_ledger_period_key", "period_month", "virtual_key_id"),
        Index("ix_spend_ledger_period_model", "period_month", "model_config_id"),
    )
