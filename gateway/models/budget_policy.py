from datetime import datetime
from decimal import Decimal
from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from gateway.db.base import Base


class BudgetPolicy(Base):
    __tablename__ = "budget_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False)  # global|team|key|model
    scope_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # FK to respective table
    monthly_limit_usd: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    action_on_breach: Mapped[str] = mapped_column(String(20), default="block")  # block|alert|both
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
