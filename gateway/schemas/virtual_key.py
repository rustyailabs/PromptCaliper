from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel


class VirtualKeyCreate(BaseModel):
    owner_label: str
    team_id: int | None = None
    monthly_budget_usd: Decimal | None = None
    budget_action: str = "block"
    rpm_limit: int | None = None
    tpm_limit: int | None = None
    allowed_models: list[str] | None = None
    expires_at: datetime | None = None


class VirtualKeyUpdate(BaseModel):
    owner_label: str | None = None
    team_id: int | None = None
    monthly_budget_usd: Decimal | None = None
    budget_action: str | None = None
    rpm_limit: int | None = None
    tpm_limit: int | None = None
    allowed_models: list[str] | None = None
    expires_at: datetime | None = None
    is_active: bool | None = None


class VirtualKeyResponse(BaseModel):
    id: int
    key_prefix: str
    owner_label: str
    team_id: int | None
    team_name: str | None = None
    monthly_budget_usd: Decimal | None
    budget_action: str
    rpm_limit: int | None
    tpm_limit: int | None
    allowed_models: list[str] | None
    current_spend_usd: Decimal
    budget_reset_at: datetime
    expires_at: datetime | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class VirtualKeyCreateResponse(VirtualKeyResponse):
    """Returned once at creation — includes the full key value."""
    full_key: str
