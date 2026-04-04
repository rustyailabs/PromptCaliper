from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel


class ModelConfigCreate(BaseModel):
    litellm_model_name: str
    display_name: str
    provider: str
    api_base: str | None = None
    api_key_env_var: str | None = None  # optional for local/Ollama models
    routing_weight: int = 1
    fallback_priority: int | None = None
    max_tokens: int | None = None
    temperature_default: Decimal | None = None
    cost_per_input_token: Decimal | None = None
    cost_per_output_token: Decimal | None = None
    context_window: int | None = None


class ModelConfigUpdate(BaseModel):
    litellm_model_name: str | None = None
    display_name: str | None = None
    provider: str | None = None
    api_base: str | None = None
    api_key_env_var: str | None = None
    routing_weight: int | None = None
    fallback_priority: int | None = None
    max_tokens: int | None = None
    temperature_default: Decimal | None = None
    cost_per_input_token: Decimal | None = None
    cost_per_output_token: Decimal | None = None
    context_window: int | None = None
    is_active: bool | None = None
    status: str | None = None


class ModelConfigResponse(BaseModel):
    id: int
    litellm_model_name: str
    display_name: str
    provider: str
    api_base: str | None
    api_key_env_var: str | None
    routing_weight: int
    fallback_priority: int | None
    max_tokens: int | None
    temperature_default: Decimal | None
    cost_per_input_token: Decimal | None
    cost_per_output_token: Decimal | None
    context_window: int | None
    avg_latency_ms: int | None
    is_active: bool
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
