# PromptCaliper — AI Gateway & Observability Platform

PromptCaliper is a self-hosted AI gateway that acts as a single point of entry for all LLM traffic in your organisation. Built on [LiteLLM](https://www.litellm.ai/) and a custom FastAPI backend, it gives you unified routing, spend enforcement, rate limiting, guardrails, response caching, and a full audit trail — all managed from a single React admin console.

> **Architecture overview:** see [`docs/architecture.html`](docs/architecture.html) — open in any browser.

---

## Features

| Category | Capabilities |
|---|---|
| **Routing** | LiteLLM Router — load balancing, fallbacks, retries across OpenAI · Anthropic · Azure · Gemini · Bedrock · Ollama |
| **Virtual Keys** | SHA-256-hashed API keys per user/service; full key shown once at creation only; per-key spend tracking |
| **Budget Control** | Per-key, per-team, per-model, global monthly limits — block / alert / block+alert on breach |
| **Rate Limiting** | RPM & TPM enforcement per virtual key; DB-backed (survives restarts); live usage counters |
| **Guardrails** | Keyword block, regex filter, PII redaction, content category filter — applied pre- and post-LLM call; live test panel |
| **Caching** | Exact-match local (in-memory) or Redis caching; semantic similarity caching via LiteLLM; hit rate tracking |
| **Observability** | Full prompt/response audit log, token & cost tracking, latency, cache hit/miss, Request Inspection modal |
| **Analytics** | Spend by team/model/key, token economics (7d), model distribution, 6-month org spend chart |
| **Alerts** | Threshold rules on spend %, budget remaining, error rate, latency p99 — notify via log / email (SMTP) / webhook / Slack Incoming Webhook; 30-minute per-rule cooldown to prevent spam |
| **Auth** | JWT username/password login; 15-min access + 7-day refresh token rotation; server-side logout blocklist |

---

## Quick-start — Local Development (SQLite + in-memory rate limiting)

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) ≥ 4.x
- OR: Python 3.12+ and Node 22+ (if running without Docker)

### Option A — Docker Compose (recommended)

```bash
# 1. Clone
git clone https://github.com/your-org/promptcaliper.git
cd promptcaliper

# 2. Configure environment
cp gateway/.env.example gateway/.env
# Edit gateway/.env — set JWT_SECRET_KEY and SUPERADMIN_PASSWORD at minimum
# Add at least one LLM provider key (OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.)

# 3. Start everything
docker compose -f docker-compose.dev.yml up --build

# Frontend   → http://localhost:5173
# Backend API → http://localhost:8000
# Swagger docs → http://localhost:8000/docs  (only when DEBUG=true)
```

Default superadmin credentials (from `gateway/.env`):
- **Username:** `admin`
- **Password:** whatever you set in `SUPERADMIN_PASSWORD`

### Option B — Manual (no Docker)

**Backend**

```bash
cd gateway
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Create .env from example and fill in values
cp .env.example .env

# Run from the REPO ROOT so that 'gateway' resolves as a Python package
cd ..
uvicorn gateway.main:app --reload --port 8000
```

**Frontend**

```bash
# From the repo root
npm install
npm run dev
# → http://localhost:5173
```

### Minimum required environment variables

```dotenv
# gateway/.env
DATABASE_URL=sqlite+aiosqlite:///./gateway.db
JWT_SECRET_KEY=any-long-random-string-change-me
SUPERADMIN_USERNAME=admin
SUPERADMIN_PASSWORD=changeme
SUPERADMIN_EMAIL=admin@example.com
RATE_LIMIT_BACKEND=memory

# At least one LLM provider key:
OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
# GEMINI_API_KEY=...
# OLLAMA_API_BASE=http://localhost:11434
```

> **Tip:** On first startup the gateway auto-seeds default model configs for every provider key it finds. Add a key to `.env`, restart, and the model appears in Model Registry automatically.

---

## Production Deployment (PostgreSQL + Redis + nginx)

### Prerequisites

- Docker Compose v2 on the target server
- A domain name pointed at the server (optional — HTTP works too)

### Step 1 — Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set **all required** values:

| Variable | Required | Notes |
|---|---|---|
| `POSTGRES_PASSWORD` | ✅ | Strong random password |
| `JWT_SECRET_KEY` | ✅ | `openssl rand -hex 32` |
| `SUPERADMIN_PASSWORD` | ✅ | Admin console password |
| `OPENAI_API_KEY` | at least one | Or any other provider key |
| `DOMAIN` | optional | Used in nginx CORS config |
| `CORS_ORIGINS` | optional | JSON list e.g. `["https://yourdomain.com"]` |
| `SMTP_HOST` | optional | SMTP server hostname for email alert notifications |
| `SMTP_PORT` | optional | SMTP port (default: `587`) |
| `SMTP_USER` | optional | SMTP username / sender address |
| `SMTP_PASSWORD` | optional | SMTP password |
| `SMTP_FROM` | optional | Sender address override (defaults to `SMTP_USER`) |

> **Security enforcement:** When `DEBUG=false` (all production deployments), the gateway **refuses to start** if `JWT_SECRET_KEY` or `SUPERADMIN_PASSWORD` are still set to their placeholder defaults. Set strong values before first boot.

### Step 2 — Build and start

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

Services started:

| Service | Description |
|---|---|
| `postgres` | PostgreSQL 16 — persistent data volume |
| `redis` | Redis 7 — rate limiting counters + response cache store |
| `gateway` | FastAPI + LiteLLM (2 uvicorn workers) |
| `frontend` | Pre-built React SPA served by nginx |
| `nginx` | Reverse proxy — port 80 → `/api/*` to gateway, `/` to frontend |

### Step 3 — Verify

```bash
# Health check (also verifies DB connectivity — returns 503 if DB is unreachable)
curl http://localhost/api/health
# → {"status":"ok","version":"2.0.0","database":"ok"}

# Login and get token
curl -X POST http://localhost/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"<your-password>"}'
# → {"access_token":"...","token_type":"bearer"}

# Open admin console
open http://localhost
```

### Step 4 — Send a test completion

```bash
# Create a virtual key in the admin console, then:
curl http://localhost/api/v1/chat/completions \
  -H 'Authorization: Bearer sk-ft-<your-virtual-key>' \
  -H 'Content-Type: application/json' \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"Hello!"}]}'
```

### Scaling notes

- **Multiple gateway replicas:** rate limiting via Redis is shared across all workers automatically.
- **PostgreSQL backups:** use `pg_dump` via cron or a managed backup service on the `postgres_data` volume.
- **TLS:** add a `certbot` container or place an external load balancer (AWS ALB, Cloudflare) in front of nginx.
- **Alembic migrations:** run `alembic upgrade head` inside the gateway container before deploying schema changes.

### Useful ops commands

```bash
# View gateway logs
docker compose -f docker-compose.prod.yml logs -f gateway

# Reset superadmin password
docker compose -f docker-compose.prod.yml exec gateway \
  python -m gateway.scripts.seed_admin

# Manually trigger monthly budget reset
docker compose -f docker-compose.prod.yml exec gateway \
  python -m gateway.scripts.reset_monthly_budgets

# Open psql shell
docker compose -f docker-compose.prod.yml exec postgres \
  psql -U promptcaliper -d promptcaliper

# Run test completions against the live stack
docker compose -f docker-compose.prod.yml exec gateway \
  python -m gateway.scripts.test_chat --token <JWT> --diagnose
```

---

## API Reference

All management endpoints require an admin JWT (`Authorization: Bearer <token>` from `/api/auth/login`).
Chat completion endpoints accept either a JWT **or** a virtual key (`sk-ft-...`).

### Authentication

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/auth/login` | Username + password → access + refresh tokens. Rate-limited to **10 attempts per 60s per IP** — returns 429 + `Retry-After` header on breach. |
| `POST` | `/api/auth/refresh` | Rotate refresh token |
| `POST` | `/api/auth/logout` | Invalidate refresh token server-side |
| `GET` | `/api/auth/me` | Current user info |

### Chat Completions

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/v1/chat/completions` | Virtual key or JWT | OpenAI-compatible completion endpoint |

**Request body:**
```json
{
  "model": "gpt-4o-mini",
  "messages": [{"role": "user", "content": "Hello!"}],
  "temperature": 0.7,
  "max_tokens": 1024
}
```

### Management Endpoints

| Resource | Base Path | Operations |
|---|---|---|
| Models | `/api/models` | CRUD model configs, toggle active |
| Virtual Keys | `/api/virtual-keys` | CRUD keys, view spend |
| Teams | `/api/teams` | CRUD teams with monthly budget |
| Users | `/api/users` | Admin user management |
| Rate Limits | `/api/rate-limits` | CRUD policies; `GET /current-usage` for live RPM/TPM |
| Budgets | `/api/budgets` | CRUD policies; spend by team/model/key; org summary |
| Guardrails | `/api/guardrails` | CRUD rules; `POST /test` for live testing |
| Cache | `/api/cache` | `GET/PUT /config`; `GET /stats`; `DELETE /clear` |
| Logs | `/api/logs` | Paginated log with filters (status, cache, search) |
| Analytics | `/api/analytics` | Overview KPIs, timeseries, model distribution, token economics |
| Alerts | `/api/alerts` | CRUD alert rules |
| Health | `/api/health` | Liveness + readiness check — verifies DB connectivity; returns `503` if the database is unreachable |

---

## Test Script

`gateway/scripts/test_chat.py` is a CLI tool for testing the gateway without the admin console:

```bash
# Run from repo root with the virtual environment active

# 1. Diagnose — check gateway health and list configured models
python -m gateway.scripts.test_chat --token <JWT> --diagnose

# 2. List all active models
python -m gateway.scripts.test_chat --token <JWT> --list-models

# 3. Send a test completion with a virtual key
python -m gateway.scripts.test_chat \
  --key sk-ft-<your-key> \
  --model gpt-4o-mini \
  --prompt "Explain caching in one sentence"

# 4. Custom parameters
python -m gateway.scripts.test_chat \
  --key sk-ft-<your-key> \
  --model gpt-4o-mini \
  --temperature 0.2 \
  --max-tokens 256

# 5. Register a new model
python -m gateway.scripts.test_chat \
  --token <JWT> \
  --add-model "My Ollama" \
  --litellm-model "ollama/llama3" \
  --provider ollama
```

**Arguments:**

| Flag | Description |
|---|---|
| `--key` | Virtual key (`sk-ft-...`) — for completions |
| `--token` | Admin JWT — for management operations |
| `--model` | Model display name to call |
| `--prompt` | Test prompt (default: "Hello, what can you do?") |
| `--temperature` | Sampling temperature (default: 0.7) |
| `--max-tokens` | Max completion tokens |
| `--host` | Gateway host (default: localhost) |
| `--port` | Gateway port (default: 8000) |
| `--list-models` | List all active model configs |
| `--diagnose` | Run health + model validation checks |
| `--add-model` | Register a new model (requires `--litellm-model`, `--provider`) |

---

## Feature Details

### Guardrails

Guardrails run on every request before it reaches the LLM (input) and on the response (output). Four types are supported:

| Type | Config JSON | Effect |
|---|---|---|
| `keyword_block` | `{"keywords": ["word1", "word2"]}` | Blocks or flags requests/responses containing any keyword |
| `regex_filter` | `{"pattern": "\\bsensitive\\b"}` | Blocks or flags text matching the regex. Patterns are evaluated with a **1-second timeout** to prevent ReDoS attacks from pathological patterns. |
| `pii_redaction` | `{}` | Replaces emails, SSNs, phone numbers, and credit card numbers with `[EMAIL]`, `[SSN]`, `[PHONE]`, `[CARD]` |
| `content_filter` | `{"categories": ["violence", "adult"]}` | Blocks requests matching built-in category keyword lists |

**Actions:** `block` (reject with 400), `redact` (modify in place), `flag` (pass through but mark).
**Applies to:** `input`, `output`, or `both`.

**Request limits:** each request may contain at most **100 messages**; each message content is capped at **100,000 characters**.

Use the **Test** button in the Guardrails view to validate rules against a sample prompt before enabling them.

### Caching

Response caching is configured in the Cache view and applies globally:

| Cache Type | Backed by | Notes |
|---|---|---|
| Local (in-memory) | Python dict | Fast; cleared on gateway restart. Good for development. |
| Redis | Redis 7 | Persistent across restarts; shared across multiple workers. |
| Redis Semantic | Redis + embeddings | Matches semantically similar (not just identical) prompts. |

The Cache view shows live runtime status (active/inactive), current backend type, number of cached entries, total hits/misses, hit rate, and estimated cost savings. Savings are computed from the original token cost of cached responses.

> Cache hits are tracked per-request in the audit log and contribute to the Hit Rate metric.

### Rate Limiting

Rate limits are enforced at the virtual key level:
- **RPM** (requests per minute) and **TPM** (tokens per minute) limits per key
- Limits are checked against the last 60 seconds of `request_logs` — DB-backed, survives gateway restarts
- Blocked requests return **HTTP 429** with a `Retry-After` header indicating seconds until the window resets; they are logged and visible in the Logs view and dashboard
- Live usage counters in Rate Limiting view show current-minute RPM and TPM per key

### Budget Enforcement

Monthly spend limits can be set at four scopes:

| Scope | Description |
|---|---|
| `global` | Total org spend cap |
| `team` | Spend cap per team |
| `key` | Spend cap per virtual key |
| `model` | Spend cap per model |

On breach: `block` (HTTP 429), `alert` (notify only), or `both`.
Budgets reset automatically on the 1st of each month at 00:05 UTC via APScheduler.

---

## Project Structure

```
promptcaliper/
├── gateway/                        # FastAPI backend (Python package)
│   ├── main.py                     # App factory, lifespan, APScheduler scheduler
│   ├── config.py                   # pydantic-settings — all environment variables
│   ├── auth/                       # JWT login, refresh, logout, /me
│   ├── callbacks/                  # LiteLLM hooks: request logging + budget enforcement
│   ├── db/                         # SQLAlchemy engine + async session factory
│   ├── models/                     # ORM models (one file per domain entity)
│   ├── routers/                    # API routers (one file per domain)
│   ├── schemas/                    # Pydantic request/response models
│   ├── services/                   # Business logic (LiteLLM, keys, spend, alerts, cache…)
│   ├── scripts/
│   │   ├── test_chat.py            # CLI tool: test completions, list models, diagnostics
│   │   ├── seed_admin.py           # Bootstrap or reset the superadmin user
│   │   └── reset_monthly_budgets.py# Manual trigger for monthly budget reset
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── src/                            # React 19 frontend
│   ├── components/
│   │   ├── shared/                 # LoadingSpinner, ErrorBanner, FormModal, PromptModal, …
│   │   └── views/                  # 11 view components (one per sidebar tab)
│   ├── context/                    # AuthContext, ThemeContext (dark/light mode)
│   ├── hooks/                      # usePolling (30s auto-refresh), useAuth
│   ├── services/                   # Axios API wrappers (one per domain)
│   ├── styles/
│   │   └── RustyStyles.jsx         # CSS custom properties, dark/light theme variables
│   ├── App.jsx                     # Auth gate, sidebar navigation, view routing
│   └── main.jsx                    # Root — AuthProvider > ThemeProvider > App
├── docs/
│   └── architecture.html           # Interactive architecture & data-flow diagram
├── public/
│   └── promptcaliper.svg              # App logo / favicon
├── docker-compose.dev.yml          # Dev stack (SQLite, hot-reload, no Redis)
├── docker-compose.prod.yml         # Prod stack (PostgreSQL 16, Redis 7, nginx)
├── Dockerfile.frontend             # Multi-stage: Node 22 build → nginx 1.25 serve
├── nginx.conf                      # Reverse proxy: /api/* → gateway, / → frontend
├── .env.example                    # Root env template for prod Compose
├── package.json                    # Node dependencies (React, Vite, Tailwind, Recharts)
└── vite.config.js                  # Vite bundler configuration
```

---

## Admin Console Views

| View | Sidebar Section | Description |
|---|---|---|
| Overview | Observability | KPI cards (requests, latency, cost, cache hit rate), live request chart, model distribution, recent logs |
| Request Logs | Observability | Paginated audit log; inline prompt/response expansion; Request Inspection modal with full token breakdown |
| Analytics | Observability | Org spend by team (6 months), token economics (7d input vs output), model cost distribution pie |
| Virtual Keys | Gateway | Create/rotate/delete API keys; per-key spend vs budget progress bar |
| Budget & Spend | Gateway | Org spend summary (tokens + USD), spend by team/model/key, budget policy CRUD |
| Rate Limiting | Gateway | RPM/TPM policy CRUD; live current-minute usage table per key |
| Model Registry | Gateway | Register LLM models across providers; toggle active; set routing weights and fallback priority |
| Guardrails | Safety | Add/toggle content filter rules; test panel for live rule validation |
| Cache | Safety | Enable/configure response caching (local/Redis/semantic); live runtime status, entry count, hit rate |
| Alerts | Safety | Threshold alert rules → notify via log / email / webhook / Slack |
| Users | Admin | Admin user management (create, search, delete) |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19, Vite, Tailwind CSS v4, Recharts, Lucide React |
| Backend | FastAPI, Python 3.12, LiteLLM ≥ 1.40, APScheduler |
| Database | SQLAlchemy 2 async — SQLite (dev) / PostgreSQL 16 (prod) |
| Auth | python-jose JWT, passlib bcrypt, refresh-token rotation |
| Cache / Rate limit | Redis 7 (prod) / in-memory (dev) |
| Container | Docker Compose v2, multi-stage Dockerfile, nginx 1.25 |

---

## Supported LLM Providers

| Provider | Env Variable | Example Model |
|---|---|---|
| OpenAI | `OPENAI_API_KEY` | `gpt-4o`, `gpt-4o-mini` |
| Anthropic | `ANTHROPIC_API_KEY` | `claude-3-5-sonnet-20241022` |
| Azure OpenAI | `AZURE_API_KEY` + `AZURE_API_BASE` | `azure/gpt-4o` |
| Google Gemini | `GEMINI_API_KEY` | `gemini/gemini-1.5-flash` |
| AWS Bedrock | `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` | `bedrock/anthropic.claude-3` |
| Ollama (local) | `OLLAMA_API_BASE` | `ollama/llama3`, `ollama/mistral` |

Models are registered in the **Model Registry** view and can be enabled/disabled at runtime without restarting.

---

## License

MIT — see [LICENSE](LICENSE).
