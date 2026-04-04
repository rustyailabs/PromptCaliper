from datetime import datetime, timezone, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, outerjoin
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.db.session import get_db
from gateway.dependencies import get_current_user
from gateway.models.request_log import RequestLog
from gateway.models.spend_ledger import SpendLedger
from gateway.models.team import Team
from gateway.services.spend_service import (
    _date_bucket_expr,
    get_org_spend,
    get_spend_by_model,
    get_spend_by_team,
    get_timeseries,
)

router = APIRouter(dependencies=[Depends(get_current_user)])

# Valid time-range values — validated explicitly to avoid silent fallback
TimeRange = Literal["1h", "24h", "7d", "30d"]

_DELTA_MAP: dict[str, timedelta] = {
    "1h": timedelta(hours=1),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}


def _time_range(time_range: TimeRange) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    return now - _DELTA_MAP[time_range], now


@router.get("/overview")
async def overview(
    time_range: TimeRange = Query("24h"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from_dt, to_dt = _time_range(time_range)

    result = await db.execute(
        select(
            func.count(RequestLog.id).label("total"),
            func.coalesce(func.avg(RequestLog.latency_ms), 0).label("avg_latency"),
            func.coalesce(func.sum(RequestLog.cost_usd), 0).label("total_cost"),
            func.coalesce(func.sum(RequestLog.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(RequestLog.prompt_tokens), 0).label("prompt_tokens"),
            func.coalesce(func.sum(RequestLog.completion_tokens), 0).label("completion_tokens"),
        ).where(RequestLog.started_at >= from_dt, RequestLog.started_at <= to_dt)
    )
    row = result.one()

    # Error and blocked counts
    err_result = await db.execute(
        select(func.count(RequestLog.id)).where(
            RequestLog.started_at >= from_dt,
            RequestLog.status_code >= 400,
        )
    )
    error_count = err_result.scalar() or 0

    blocked_result = await db.execute(
        select(func.count(RequestLog.id)).where(
            RequestLog.started_at >= from_dt,
            RequestLog.status_code == 429,
        )
    )
    blocked_count = blocked_result.scalar() or 0

    cache_result = await db.execute(
        select(func.count(RequestLog.id)).where(
            RequestLog.started_at >= from_dt,
            RequestLog.cache_hit == True,
        )
    )
    cache_hits = cache_result.scalar() or 0

    total = int(row.total or 0)
    return {
        "total_requests": total,
        "avg_latency_ms": round(float(row.avg_latency or 0)),
        "total_cost_usd": float(row.total_cost or 0),
        "total_tokens": int(row.total_tokens or 0),
        "prompt_tokens": int(row.prompt_tokens or 0),
        "completion_tokens": int(row.completion_tokens or 0),
        "error_count": int(error_count),
        "blocked_count": int(blocked_count),
        "cache_hits": int(cache_hits),
        "cache_hit_rate": round(cache_hits / total * 100, 1) if total else 0,
    }


@router.get("/timeseries")
async def timeseries(
    time_range: TimeRange = Query("24h"),
    granularity: str = Query("hour"),
    db: AsyncSession = Depends(get_db),
) -> list:
    from_dt, to_dt = _time_range(time_range)
    return await get_timeseries(db, from_dt, to_dt, granularity)


@router.get("/model-distribution")
async def model_distribution(
    time_range: TimeRange = Query("24h"),
    db: AsyncSession = Depends(get_db),
) -> list:
    from_dt, to_dt = _time_range(time_range)
    result = await db.execute(
        select(
            RequestLog.litellm_model_name,
            func.count(RequestLog.id).label("count"),
            func.coalesce(func.sum(RequestLog.cost_usd), 0).label("cost"),
        )
        .where(RequestLog.started_at >= from_dt, RequestLog.started_at <= to_dt)
        .group_by(RequestLog.litellm_model_name)
        .order_by(func.count(RequestLog.id).desc())
    )
    rows = result.all()
    total = sum(r.count for r in rows)
    return [
        {
            "model": row.litellm_model_name,
            "request_count": int(row.count),
            "pct": round(row.count / total * 100, 1) if total else 0,
            "cost_usd": float(row.cost),
        }
        for row in rows
    ]


@router.get("/team-spend")
async def team_spend_history(
    months: int = Query(6, ge=1, le=24),
    db: AsyncSession = Depends(get_db),
) -> list:
    """Monthly spend per team for last N months — for stacked bar chart.

    Correctly handles year roll-overs for any value of `months` (up to 24).
    Uses an OUTER join so unassigned-team spend appears in the result as well.
    """
    now = datetime.now(timezone.utc)

    # Build period strings by stepping back month-by-month from today.
    # Using timedelta(days=32) + replace(day=1) is simpler and avoids
    # manual year-wrap arithmetic.
    periods: list[str] = []
    cursor = now.replace(day=1)
    for _ in range(months):
        periods.append(cursor.strftime("%Y-%m"))
        # Move to the first of the previous month
        prev = (cursor - timedelta(days=1)).replace(day=1)
        cursor = prev
    periods.reverse()  # oldest → newest

    result = await db.execute(
        select(
            SpendLedger.period_month,
            Team.name,
            func.sum(SpendLedger.amount_usd).label("spend"),
        )
        # Outer join: include SpendLedger rows even without a matching Team
        .outerjoin(Team, SpendLedger.team_id == Team.id)
        .where(SpendLedger.period_month.in_(periods))
        .group_by(SpendLedger.period_month, Team.name)
        .order_by(SpendLedger.period_month)
    )
    rows = result.all()

    # Pivot to [{month, team1: $X, team2: $Y, …}]
    pivot: dict[str, dict] = {p: {"month": p} for p in periods}
    for row in rows:
        team_name = row.name or "Unassigned"
        pivot[row.period_month][team_name] = float(row.spend)
    return list(pivot.values())


@router.get("/token-economics")
async def token_economics(
    days: int = Query(7, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
) -> list:
    """Daily input/output token split — dialect-aware date truncation."""
    from_dt = datetime.now(timezone.utc) - timedelta(days=days)

    dialect = (db.bind.dialect.name if db.bind else "sqlite")
    day_expr = _date_bucket_expr(RequestLog.started_at, "day", dialect)

    result = await db.execute(
        select(
            day_expr.label("day"),
            func.coalesce(func.sum(RequestLog.prompt_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(RequestLog.completion_tokens), 0).label("output_tokens"),
        )
        .where(RequestLog.started_at >= from_dt)
        .group_by("day")
        .order_by("day")
    )
    return [
        {"day": row.day, "input_tokens": int(row.input_tokens), "output_tokens": int(row.output_tokens)}
        for row in result.all()
    ]
