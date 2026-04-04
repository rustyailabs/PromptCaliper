from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel


class BudgetPolicyCreate(BaseModel):
    name: str
    scope_type: str  # global|team|key|model
    scope_id: int | None = None
    monthly_limit_usd: Decimal
    action_on_breach: str = "block"


class BudgetPolicyUpdate(BaseModel):
    name: str | None = None
    monthly_limit_usd: Decimal | None = None
    action_on_breach: str | None = None
    is_active: bool | None = None


class BudgetPolicyResponse(BaseModel):
    id: int
    name: str
    scope_type: str
    scope_id: int | None
    monthly_limit_usd: Decimal
    action_on_breach: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class SpendSummary(BaseModel):
    scope_type: str
    scope_id: int | None
    scope_name: str | None
    period_month: str
    total_spend_usd: Decimal
    budget_limit_usd: Decimal | None
    spend_pct: float | None
    prompt_tokens: int
    completion_tokens: int
