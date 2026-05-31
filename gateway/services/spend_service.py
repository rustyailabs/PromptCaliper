"""Spend aggregation over Firestore request and ledger collections."""
from datetime import datetime, timezone

from gateway.firestore_store import FirestoreStore


def _current_period() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _bucket(dt: datetime, granularity: str) -> str:
    return dt.strftime("%Y-%m-%d %H") if granularity == "hour" else dt.strftime("%Y-%m-%d")


def get_org_spend(db: FirestoreStore, period_month: str | None = None) -> dict:
    period = period_month or _current_period()
    rows = [r for r in db.list("spend_ledger") if r.period_month == period]
    return {
        "period_month": period,
        "total_spend_usd": sum(float(r.amount_usd or 0) for r in rows),
        "prompt_tokens": sum(int(r.prompt_tokens or 0) for r in rows),
        "completion_tokens": sum(int(r.completion_tokens or 0) for r in rows),
    }


def get_spend_by_team(db: FirestoreStore, period_month: str | None = None) -> list[dict]:
    period = period_month or _current_period()
    ledger = [r for r in db.list("spend_ledger") if r.period_month == period]
    out = []
    for team in db.list("teams", order_by="name"):
        rows = [r for r in ledger if r.team_id == team.id]
        spend = sum(float(r.amount_usd or 0) for r in rows)
        limit = float(team.monthly_budget_usd) if getattr(team, "monthly_budget_usd", None) else None
        out.append({
            "team_id": team.id,
            "team_name": team.name,
            "spend_usd": spend,
            "budget_usd": limit,
            "spend_pct": round((spend / limit * 100), 1) if limit else None,
            "prompt_tokens": sum(int(r.prompt_tokens or 0) for r in rows),
            "completion_tokens": sum(int(r.completion_tokens or 0) for r in rows),
        })
    return out


def get_spend_by_model(db: FirestoreStore, period_month: str | None = None) -> list[dict]:
    period = period_month or _current_period()
    logs = [
        r for r in db.list("request_logs")
        if r.started_at.strftime("%Y-%m") == period and r.status_code == 200
    ]
    grouped: dict[str, dict] = {}
    for log in logs:
        model = log.litellm_model_name or "unknown"
        item = grouped.setdefault(model, {"model_name": model, "spend_usd": 0.0, "total_tokens": 0, "requests": 0})
        item["spend_usd"] += float(log.cost_usd or 0)
        item["total_tokens"] += int(log.total_tokens or 0)
        item["requests"] += 1
    return sorted(grouped.values(), key=lambda r: r["total_tokens"], reverse=True)


def get_spend_by_key(db: FirestoreStore, period_month: str | None = None) -> list[dict]:
    period = period_month or _current_period()
    ledger = [r for r in db.list("spend_ledger") if r.period_month == period]
    out = []
    for key in db.list("virtual_keys"):
        rows = [r for r in ledger if r.virtual_key_id == key.id]
        spend = sum(float(r.amount_usd or 0) for r in rows)
        limit = float(key.monthly_budget_usd) if getattr(key, "monthly_budget_usd", None) else None
        out.append({
            "key_id": key.id,
            "key_prefix": key.key_prefix,
            "owner_label": key.owner_label,
            "spend_usd": spend,
            "budget_usd": limit,
            "spend_pct": round((spend / limit * 100), 1) if limit else None,
        })
    return out


def get_timeseries(
    db: FirestoreStore,
    from_dt: datetime,
    to_dt: datetime,
    granularity: str = "day",
) -> list[dict]:
    grouped: dict[str, dict] = {}
    for log in db.list("request_logs"):
        if not (from_dt <= log.started_at <= to_dt):
            continue
        key = _bucket(log.started_at, granularity)
        item = grouped.setdefault(key, {"time": key, "requests": 0, "cost_usd": 0.0, "tokens": 0})
        item["requests"] += 1
        item["cost_usd"] += float(log.cost_usd or 0)
        item["tokens"] += int(log.total_tokens or 0)
    return [grouped[k] for k in sorted(grouped)]
