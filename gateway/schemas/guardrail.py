from datetime import datetime
from pydantic import BaseModel


class GuardrailCreate(BaseModel):
    name: str
    guardrail_type: str  # pii_redaction|content_filter|keyword_block|regex_filter|prompt_injection
    applies_to: str = "both"  # input|output|both
    config_json: dict = {}
    action_on_trigger: str = "block"  # block|redact|flag|rewrite


class GuardrailUpdate(BaseModel):
    name: str | None = None
    applies_to: str | None = None
    config_json: dict | None = None
    action_on_trigger: str | None = None
    is_active: bool | None = None


class GuardrailResponse(BaseModel):
    id: int
    name: str
    guardrail_type: str
    applies_to: str
    config_json: dict
    action_on_trigger: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class GuardrailTestRequest(BaseModel):
    messages: list[dict]
    test_content: str = ""


class GuardrailTestResponse(BaseModel):
    triggered: bool
    triggered_by: list[str]
    processed_messages: list[dict]
