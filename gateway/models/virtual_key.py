from datetime import datetime
from decimal import Decimal
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gateway.db.base import Base


class VirtualKey(Base):
    __tablename__ = "virtual_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    key_prefix: Mapped[str] = mapped_column(String(30), nullable=False)  # "sk-ft-abc1...xyz4" for display
    created_by_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("admin_users.id"), nullable=True, index=True)
    team_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("teams.id"), nullable=True, index=True)
    owner_label: Mapped[str] = mapped_column(String(100), nullable=False)  # "alice.chen" or "svc-bot-01"
    monthly_budget_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    budget_action: Mapped[str] = mapped_column(String(20), default="block")  # block | alert | both
    rpm_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tpm_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    allowed_models: Mapped[list | None] = mapped_column(JSON, nullable=True)  # null = all models allowed
    current_spend_usd: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0.0"))
    budget_reset_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    team = relationship("Team", foreign_keys=[team_id], lazy="selectin")
