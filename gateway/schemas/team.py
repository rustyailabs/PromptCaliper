from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel


class TeamCreate(BaseModel):
    name: str
    description: str | None = None
    monthly_budget_usd: Decimal | None = None
    budget_action: str = "block"


class TeamUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    monthly_budget_usd: Decimal | None = None
    budget_action: str | None = None
    is_active: bool | None = None


class TeamResponse(BaseModel):
    id: int
    name: str
    description: str | None
    monthly_budget_usd: Decimal | None
    budget_action: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
