# Firestore Schema — PromptCaliper Gateway

**GCP project:** `emerald-spring-486005-r4`  
**Database ID:** `promptcaliper` (named database — not `(default)`)

Firestore has no enforced schema. Collections and fields below match what the gateway reads and writes. Pydantic schemas live in `gateway/schemas/` unless noted.

## Document IDs

| Pattern | Collections |
|---------|-------------|
| Auto-increment integer via `_counters/{collection}` | Most collections (`admin_users`, `virtual_keys`, `model_configs`, …) |
| Fixed singleton `1` | `system_config`, `cache_configs` (optional — created on first PUT if missing) |
| String UUID / opaque | `refresh_token_blocklist.jti`, `request_logs.request_id` |

Every document also gets `id`, `created_at`, and `updated_at` from `FirestoreStore.set()`.

---

## Collections

### `admin_users`

Login accounts for the management UI.

| Field | Type | Notes |
|-------|------|-------|
| `id` | int | Auto |
| `username` | string | Unique |
| `email` | string | |
| `hashed_password` | string | bcrypt |
| `is_superadmin` | bool | |
| `is_active` | bool | |
| `last_login_at` | timestamp \| null | |
| `created_at` | timestamp | |
| `updated_at` | timestamp | |

**API schema:** `gateway/auth/schemas.py` → `AdminUserResponse`  
**Seeded on boot:** one superadmin from `.env` (`SUPERADMIN_*`) if none exists.

---

### `refresh_token_blocklist`

Revoked refresh tokens (logout).

| Field | Type | Notes |
|-------|------|-------|
| `id` | int | Auto |
| `jti` | string | JWT ID |
| `expires_at` | timestamp | |
| `created_at` | timestamp | |
| `updated_at` | timestamp | |

**Written by:** auth logout flow (`gateway/auth/service.py`).

---

### `system_config`

Singleton runtime settings.

| Field | Type | Notes |
|-------|------|-------|
| `id` | int | Always `1` |
| `log_prompt_content` | bool | Whether to store prompt/response text in logs |
| `created_at` | timestamp | |
| `updated_at` | timestamp | |

**API:** `PATCH /api/users/runtime-settings`  
**Not seeded on boot** — create via UI or API when needed.

---

### `cache_configs`

LiteLLM response cache settings.

| Field | Type | Notes |
|-------|------|-------|
| `id` | int | Usually `1` |
| `cache_type` | string | `in-memory`, `redis`, `semantic`, `redis-semantic` |
| `redis_url` | string \| null | |
| `semantic_similarity_threshold` | float | Default 0.95 |
| `ttl_seconds` | int | Default 3600 |
| `is_enabled` | bool | |
| `created_at` | timestamp | |
| `updated_at` | timestamp | |

**API schema:** `gateway/routers/cache.py` → `CacheConfigResponse`  
**Not seeded on boot** — created on first `PUT /api/cache/config`.

---

### `model_configs`

LLM models routed through LiteLLM.

| Field | Type | Notes |
|-------|------|-------|
| `id` | int | Auto |
| `litellm_model_name` | string | e.g. `gpt-4o-mini`, `vertex_ai/global/gemini-3.5-flash` |
| `display_name` | string | |
| `provider` | string | `openai`, `anthropic`, `gemini`, `vertex_ai`, `ollama`, … |
| `api_base` | string \| null | |
| `api_key_env_var` | string \| null | Env var name for provider key |
| `routing_weight` | int | Default 1 |
| `fallback_priority` | int \| null | |
| `max_tokens` | int \| null | |
| `temperature_default` | float \| null | |
| `cost_per_input_token` | float \| null | |
| `cost_per_output_token` | float \| null | |
| `context_window` | int \| null | |
| `avg_latency_ms` | int \| null | |
| `is_active` | bool | |
| `status` | string | e.g. `active` |
| `created_at` | timestamp | |
| `updated_at` | timestamp | |

**API schema:** `gateway/schemas/model_config.py`

---

### `guardrail_configs`

Input/output safety rules.

| Field | Type | Notes |
|-------|------|-------|
| `id` | int | Auto |
| `name` | string | |
| `guardrail_type` | string | `pii_redaction`, `content_filter`, `keyword_block`, `regex_filter`, `prompt_injection` |
| `applies_to` | string | `input`, `output`, `both` |
| `config_json` | map | Type-specific options |
| `action_on_trigger` | string | `block`, `redact`, `flag`, `rewrite` |
| `is_active` | bool | |
| `created_at` | timestamp | |
| `updated_at` | timestamp | |

**API schema:** `gateway/schemas/guardrail.py`

---

### `virtual_keys`

API keys for LLM completion requests.

| Field | Type | Notes |
|-------|------|-------|
| `id` | int | Auto |
| `key_hash` | string | SHA-256 of full key (never store plaintext) |
| `key_prefix` | string | Display prefix, e.g. `sk-ft-abc...xyz` |
| `created_by_user_id` | int | FK → `admin_users.id` |
| `team_id` | int \| null | FK → `teams.id` |
| `owner_label` | string | Human label |
| `monthly_budget_usd` | float \| null | |
| `budget_action` | string | `block`, `warn`, … |
| `rpm_limit` | int \| null | Requests per minute |
| `tpm_limit` | int \| null | Tokens per minute |
| `allowed_models` | array \| null | Model names allowed for this key |
| `current_spend_usd` | float | Denormalized running total |
| `budget_reset_at` | timestamp | Next monthly reset |
| `expires_at` | timestamp \| null | |
| `is_active` | bool | |
| `created_at` | timestamp | |
| `updated_at` | timestamp | |

**API schema:** `gateway/schemas/virtual_key.py`

---

### `teams`

Organizational grouping for keys and budgets.

| Field | Type | Notes |
|-------|------|-------|
| `id` | int | Auto |
| `name` | string | |
| `description` | string \| null | |
| `monthly_budget_usd` | float \| null | |
| `budget_action` | string | |
| `is_active` | bool | |
| `created_at` | timestamp | |
| `updated_at` | timestamp | |

**API schema:** `gateway/schemas/team.py`

---

### `budget_policies`

Named budget limits by scope.

| Field | Type | Notes |
|-------|------|-------|
| `id` | int | Auto |
| `name` | string | |
| `scope_type` | string | `global`, `team`, `key`, `model` |
| `scope_id` | int \| null | ID for scoped type |
| `monthly_limit_usd` | float | |
| `action_on_breach` | string | Default `block` |
| `is_active` | bool | |
| `created_at` | timestamp | |
| `updated_at` | timestamp | |

**API schema:** `gateway/schemas/budget.py`

---

### `rate_limit_policies`

Named rate limits by scope.

| Field | Type | Notes |
|-------|------|-------|
| `id` | int | Auto |
| `name` | string | |
| `scope_type` | string | `global`, `team`, `key` |
| `scope_id` | int \| null | |
| `rpm_limit` | int \| null | |
| `tpm_limit` | int \| null | |
| `is_active` | bool | |
| `created_at` | timestamp | |
| `updated_at` | timestamp | |

**API schema:** `gateway/schemas/rate_limit.py`

---

### `request_logs`

One row per completion request (success, failure, or blocked).

| Field | Type | Notes |
|-------|------|-------|
| `id` | int | Auto |
| `request_id` | string | UUID |
| `virtual_key_id` | int \| null | |
| `team_id` | int \| null | |
| `litellm_model_name` | string | Model actually used |
| `requested_model` | string | Model requested by client |
| `status_code` | int | |
| `prompt_messages` | array | Empty unless `log_prompt_content` is true |
| `response_content` | string \| null | Empty unless `log_prompt_content` is true |
| `prompt_tokens` | int | |
| `completion_tokens` | int | |
| `total_tokens` | int | |
| `cost_usd` | float | |
| `latency_ms` | int | |
| `cache_hit` | bool | |
| `guardrail_triggered` | bool | |
| `error_message` | string \| null | |
| `started_at` | timestamp | |
| `created_at` | timestamp | |
| `updated_at` | timestamp | |

**Written by:** `RequestLoggingCallback`, blocked-request helper in `gateway/routers/gateway.py`

---

### `spend_ledger`

Token/cost accounting linked to request logs.

| Field | Type | Notes |
|-------|------|-------|
| `id` | int | Auto |
| `request_log_id` | int | FK → `request_logs.id` |
| `virtual_key_id` | int \| null | |
| `team_id` | int \| null | |
| `model_config_id` | int \| null | |
| `amount_usd` | float | |
| `period_month` | string | `YYYY-MM` |
| `prompt_tokens` | int | |
| `completion_tokens` | int | |
| `created_at` | timestamp | |
| `updated_at` | timestamp | |

**Written by:** `RequestLoggingCallback`

---

### `alert_rules`

Threshold-based alert definitions.

| Field | Type | Notes |
|-------|------|-------|
| `id` | int | Auto |
| `name` | string | |
| `metric` | string | |
| `threshold_value` | float | |
| `scope_type` | string | Default `global` |
| `scope_id` | int \| null | |
| `notification_channel` | string | Default `log` |
| `notification_target` | string \| null | |
| `is_active` | bool | |
| `last_triggered_at` | timestamp \| null | |
| `created_at` | timestamp | |
| `updated_at` | timestamp | |

**API schema:** `gateway/routers/alerts.py` → `AlertRuleResponse`

---

### `alert_events`

Fired alert instances.

| Field | Type | Notes |
|-------|------|-------|
| `id` | int | Auto |
| `rule_id` | int \| null | FK → `alert_rules.id` |
| `rule_name` | string | |
| `metric` | string | |
| `actual_value` | float | |
| `threshold_value` | float | |
| `message` | string | |
| `fired_at` | timestamp | |
| `created_at` | timestamp | |
| `updated_at` | timestamp | |

**Written by:** `AlertService.fire_budget_alert()` and future rule evaluation.

---

### `_counters` (internal)

Auto-increment state per collection.

| Field | Type | Notes |
|-------|------|-------|
| `id` | string | Collection name |
| `value` | int | Last assigned ID |

---

## Firebase Console navigation

1. [Firebase Console](https://console.firebase.google.com/) → project linked to `emerald-spring-486005-r4`
2. **Firestore Database** → database selector → choose **`promptcaliper`**
3. Browse collections listed above (e.g. `virtual_keys`, `model_configs`)

Or in [GCP Console](https://console.cloud.google.com/firestore/databases?project=emerald-spring-486005-r4) → Firestore → select database **`promptcaliper`**.
