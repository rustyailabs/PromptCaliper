"""Spend aggregation queries from the spend_ledger and request_logs tables."""
import calendar
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.models.spend_ledger import SpendLedger
from gateway.models.team import Team
from gateway.models.virtual_key import VirtualKey


def _current_period() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _date_trunc_expr(granularity: str, column):
    """
    Return a database-agnostic date-truncation expression.
    SQLite uses strftime(); PostgreSQL uses date_trunc().
    Detected at query time via the engine dialect name stored in the session bind.
    """
    from sqlalchemy import literal_column
    from sqlalchemy.dialects import postgresql, sqlite as sqlite_dialect

    # We return a SQLAlchemy expression that works for both dialects.
    # The caller passes the compiled dialect so we choose the right form.
    return column  # placeholder — actual truncation applied in _date_bucket_expr below


def _date_bucket_expr(column, granularity: str, dialect_name: str):
    """Return a dialect-correct date-bucketing expression."""
    if dialect_name == "postgresql":
        pg_granularity = "hour" if granularity == "hour" else "day"
        return func.to_char(func.date_trunc(pg_granularity, column),
                            "YYYY-MM-DD HH24" if granularity == "hour" else "YYYY-MM-DD")
    else:
        # SQLite
        fmt = "%Y-%m-%d %H" if granularity == "hour" else "%Y-%m-%d"
        return func.strftime(fmt, column)


async def _get_dialect(db: AsyncSession) -> str:
    """Return the SQLAlchemy dialect name (e.g. 'sqlite', 'postgresql')."""
    return db.bind.dialect.name if db.bind else "sqlite"


async def get_org_spend(db: AsyncSession, period_month: str | None = None) -> dict:
    period = period_month or _current_period()
    result = await db.execute(
        select(
            func.coalesce(func.sum(SpendLedger.amount_usd), 0).label("total"),
            func.coalesce(func.sum(SpendLedger.prompt_tokens), 0).label("prompt_tokens"),
            func.coalesce(func.sum(SpendLedger.completion_tokens), 0).label("completion_tokens"),
        ).where(SpendLedger.period_month == period)
    )
    row = result.one()
    return {
        "period_month": period,
        "total_spend_usd": float(row.total),
        "prompt_tokens": int(row.prompt_tokens),
        "completion_tokens": int(row.completion_tokens),
    }


async def get_spend_by_team(db: AsyncSession, period_month: str | None = None) -> list[dict]:
    period = period_month or _current_period()
    result = await db.execute(
        select(
            Team.id,
            Team.name,
            Team.monthly_budget_usd,
            func.coalesce(func.sum(SpendLedger.amount_usd), 0).label("spend"),
            func.coalesce(func.sum(SpendLedger.prompt_tokens), 0).label("prompt_tokens"),
            func.coalesce(func.sum(SpendLedger.completion_tokens), 0).label("completion_tokens"),
        )
        .outerjoin(SpendLedger, (SpendLedger.team_id == Team.id) & (SpendLedger.period_month == period))
        .group_by(Team.id)
        .order_by(func.sum(SpendLedger.amount_usd).desc())
    )
    rows = result.all()
    out = []
    for row in rows:
        limit = float(row.monthly_budget_usd) if row.monthly_budget_usd else None
        spend = float(row.spend)
        out.append({
            "team_id": row.id,
            "team_name": row.name,
            "spend_usd": spend,
            "budget_usd": limit,
            "spend_pct": round((spend / limit * 100), 1) if limit else None,
            "prompt_tokens": int(row.prompt_tokens),
            "completion_tokens": int(row.completion_tokens),
        })
    return out


async def get_spend_by_model(db: AsyncSession, period_month: str | None = None) -> list[dict]:
    """Aggregate spend and token usage per model from request_logs for the given month."""
    from gateway.models.request_log import RequestLog

    period = period_month or _current_period()
    year, month = map(int, period.split("-"))
    last_day = calendar.monthrange(year, month)[1]
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    end = datetime(year, month, last_day, 23, 59, 59, 999999, tzinfo=timezone.utc)

    result = await db.execute(
        select(
            RequestLog.litellm_model_name.label("model_name"),
            func.coalesce(func.sum(RequestLog.cost_usd), 0).label("spend"),
            func.coalesce(func.sum(RequestLog.total_tokens), 0).label("tokens"),
            func.count(RequestLog.id).label("requests"),
        )
        .where(RequestLog.started_at >= start, RequestLog.started_at <= end, RequestLog.status_code == 200)
        .group_by(RequestLog.litellm_model_name)
        .order_by(func.sum(RequestLog.total_tokens).desc())
    )
    rows = result.all()
    return [
        {
            "model_name": row.model_name or "unknown",
            "spend_usd": float(row.spend),
            "total_tokens": int(row.tokens),
            "requests": int(row.requests),
        }
        for row in rows
    ]


async def get_spend_by_key(db: AsyncSession, period_month: str | None = None) -> list[dict]:
    period = period_month or _current_period()
    result = await db.execute(
        select(
            VirtualKey.id,
            VirtualKey.key_prefix,
            VirtualKey.owner_label,
            VirtualKey.monthly_budget_usd,
            func.coalesce(func.sum(SpendLedger.amount_usd), 0).label("spend"),
        )
        .outerjoin(SpendLedger, (SpendLedger.virtual_key_id == VirtualKey.id) & (SpendLedger.period_month == period))
        .group_by(VirtualKey.id)
        .order_by(func.sum(SpendLedger.amount_usd).desc())
    )
    rows = result.all()
    out = []
    for row in rows:
        limit = float(row.monthly_budget_usd) if row.monthly_budget_usd else None
        spend = float(row.spend)
        out.append({
            "key_id": row.id,
            "key_prefix": row.key_prefix,
            "owner_label": row.owner_label,
            "spend_usd": spend,
            "budget_usd": limit,
            "spend_pct": round((spend / limit * 100), 1) if limit else None,
        })
    return out


async def get_timeseries(
    db: AsyncSession,
    from_dt: datetime,
    to_dt: datetime,
    granularity: str = "day",
) -> list[dict]:
    """Returns spend + token timeseries grouped by day or hour.

    Uses dialect-aware date truncation to support both SQLite (dev) and
    PostgreSQL (production).
    """
    from gateway.models.request_log import RequestLog

    dialect = (db.bind.dialect.name if db.bind else "sqlite")

    bucket_expr = _date_bucket_expr(RequestLog.started_at, granularity, dialect)

    result = await db.execute(
        select(
            bucket_expr.label("bucket"),
            func.count(RequestLog.id).label("requests"),
            func.coalesce(func.sum(RequestLog.cost_usd), 0).label("cost"),
            func.coalesce(func.sum(RequestLog.total_tokens), 0).label("tokens"),
        )
        .where(RequestLog.started_at >= from_dt, RequestLog.started_at <= to_dt)
        .group_by("bucket")
        .order_by("bucket")
    )
    return [
        {
            "time": row.bucket,
            "requests": int(row.requests),
            "cost_usd": float(row.cost),
            "tokens": int(row.tokens),
        }
        for row in result.all()
    ]
