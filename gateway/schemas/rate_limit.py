from datetime import datetime
from pydantic import BaseModel


class RateLimitPolicyCreate(BaseModel):
    name: str
    scope_type: str  # global|team|key
    scope_id: int | None = None
    rpm_limit: int | None = None
    tpm_limit: int | None = None


class RateLimitPolicyUpdate(BaseModel):
    name: str | None = None
    rpm_limit: int | None = None
    tpm_limit: int | None = None
    is_active: bool | None = None


class RateLimitPolicyResponse(BaseModel):
    id: int
    name: str
    scope_type: str
    scope_id: int | None
    rpm_limit: int | None
    tpm_limit: int | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
