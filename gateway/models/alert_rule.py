from datetime import datetime
from decimal import Decimal
from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from gateway.db.base import Base


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    metric: Mapped[str] = mapped_column(String(50), nullable=False)  # spend_pct|error_rate|latency_p99|budget_remaining_usd
    threshold_value: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(20), default="global")  # global|team|key
    scope_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notification_channel: Mapped[str] = mapped_column(String(50), default="log")  # log|email|webhook
    notification_target: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AlertEvent(Base):
    """History of fired alerts."""
    __tablename__ = "alert_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    rule_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    rule_name: Mapped[str] = mapped_column(String(100), nullable=False)
    metric: Mapped[str] = mapped_column(String(50), nullable=False)
    actual_value: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    threshold_value: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    fired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
