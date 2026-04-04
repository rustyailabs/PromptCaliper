"""Alert rule evaluation and notification dispatch."""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.models.alert_rule import AlertEvent, AlertRule

logger = logging.getLogger(__name__)

# Minimum quiet period between repeated firings of the same rule (avoid alert spam)
_ALERT_COOLDOWN_MINUTES = 30


class AlertService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Ad-hoc helpers called from the budget callback ────────────────────────

    async def fire_budget_alert(self, key, current: float, limit: float) -> None:
        message = (
            f"Virtual key '{key.key_prefix}' spend ${current:.4f} "
            f"has reached budget limit ${limit:.4f}"
        )
        await self._record_and_notify(
            rule_id=None,
            rule_name="Budget Alert",
            metric="spend_pct",
            actual_value=current,
            threshold_value=limit,
            message=message,
        )

    # ── Scheduled evaluation ──────────────────────────────────────────────────

    async def evaluate_all_rules(self) -> None:
        """Called by APScheduler periodically to evaluate all active alert rules."""
        result = await self.db.execute(
            select(AlertRule).where(AlertRule.is_active == True)
        )
        rules = result.scalars().all()

        for rule in rules:
            try:
                await self._evaluate_rule(rule)
            except Exception as exc:
                logger.error("Error evaluating alert rule %s: %s", rule.id, exc)

    async def _evaluate_rule(self, rule: AlertRule) -> None:
        """Fetch the current metric value and fire the alert if the threshold is breached."""
        actual = await self._get_metric_value(rule)
        if actual is None:
            return  # metric not computable yet (e.g. no data)

        threshold = float(rule.threshold_value)
        if actual < threshold:
            return  # below threshold — nothing to do

        # Respect cooldown: skip if the rule fired recently
        if rule.last_triggered_at:
            age = datetime.now(timezone.utc) - rule.last_triggered_at.replace(
                tzinfo=timezone.utc if rule.last_triggered_at.tzinfo is None else rule.last_triggered_at.tzinfo
            )
            if age < timedelta(minutes=_ALERT_COOLDOWN_MINUTES):
                return

        message = (
            f"Alert '{rule.name}': {rule.metric} = {actual:.4f} "
            f"exceeded threshold {threshold:.4f} "
            f"(scope: {rule.scope_type}"
            + (f" id={rule.scope_id}" if rule.scope_id else "")
            + ")"
        )
        await self._record_and_notify(
            rule_id=rule.id,
            rule_name=rule.name,
            metric=rule.metric,
            actual_value=actual,
            threshold_value=threshold,
            message=message,
            channel=rule.notification_channel,
            target=rule.notification_target,
        )

        # Update last_triggered_at so we respect the cooldown on the next cycle
        rule.last_triggered_at = datetime.now(timezone.utc)

    async def _get_metric_value(self, rule: AlertRule) -> float | None:
        """Compute the current value for the rule's metric."""
        from gateway.models.request_log import RequestLog
        from gateway.models.spend_ledger import SpendLedger
        from gateway.models.virtual_key import VirtualKey
        from gateway.models.team import Team

        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=5)  # rolling 5-min window for rate metrics
        period_month = now.strftime("%Y-%m")

        metric = rule.metric

        if metric == "error_rate":
            # Percentage of requests that returned an error in the last 5 minutes
            total_q = await self.db.execute(
                select(func.count(RequestLog.id)).where(
                    RequestLog.started_at >= window_start,
                    *self._scope_filter(rule, RequestLog),
                )
            )
            total = total_q.scalar() or 0
            if total == 0:
                return None
            error_q = await self.db.execute(
                select(func.count(RequestLog.id)).where(
                    RequestLog.started_at >= window_start,
                    RequestLog.status_code >= 400,
                    *self._scope_filter(rule, RequestLog),
                )
            )
            errors = error_q.scalar() or 0
            return round(errors / total * 100, 2)

        elif metric == "latency_p99":
            # Approximate p99 latency using the 99th-percentile of recent requests
            rows_q = await self.db.execute(
                select(RequestLog.latency_ms).where(
                    RequestLog.started_at >= window_start,
                    RequestLog.status_code == 200,
                    *self._scope_filter(rule, RequestLog),
                ).order_by(RequestLog.latency_ms)
            )
            latencies = [r.latency_ms for r in rows_q.all()]
            if not latencies:
                return None
            idx = int(len(latencies) * 0.99)
            return float(latencies[min(idx, len(latencies) - 1)])

        elif metric == "spend_pct":
            # Monthly spend as a percentage of the budget for the scoped entity
            if rule.scope_type == "key" and rule.scope_id:
                key_q = await self.db.execute(
                    select(VirtualKey).where(VirtualKey.id == rule.scope_id)
                )
                key = key_q.scalar_one_or_none()
                if not key or not key.monthly_budget_usd:
                    return None
                spend_q = await self.db.execute(
                    select(func.coalesce(func.sum(SpendLedger.amount_usd), 0)).where(
                        SpendLedger.virtual_key_id == rule.scope_id,
                        SpendLedger.period_month == period_month,
                    )
                )
                spend = float(spend_q.scalar() or 0)
                return round(spend / float(key.monthly_budget_usd) * 100, 2)

            elif rule.scope_type == "team" and rule.scope_id:
                team_q = await self.db.execute(
                    select(Team).where(Team.id == rule.scope_id)
                )
                team = team_q.scalar_one_or_none()
                if not team or not team.monthly_budget_usd:
                    return None
                spend_q = await self.db.execute(
                    select(func.coalesce(func.sum(SpendLedger.amount_usd), 0)).where(
                        SpendLedger.team_id == rule.scope_id,
                        SpendLedger.period_month == period_month,
                    )
                )
                spend = float(spend_q.scalar() or 0)
                return round(spend / float(team.monthly_budget_usd) * 100, 2)

            else:
                # Global: no meaningful budget % without a global budget config
                return None

        elif metric == "budget_remaining_usd":
            # Remaining budget in USD for the scoped entity
            if rule.scope_type == "key" and rule.scope_id:
                key_q = await self.db.execute(
                    select(VirtualKey).where(VirtualKey.id == rule.scope_id)
                )
                key = key_q.scalar_one_or_none()
                if not key or not key.monthly_budget_usd:
                    return None
                return max(0.0, float(key.monthly_budget_usd) - float(key.current_spend_usd or 0))

            elif rule.scope_type == "team" and rule.scope_id:
                team_q = await self.db.execute(
                    select(Team).where(Team.id == rule.scope_id)
                )
                team = team_q.scalar_one_or_none()
                if not team or not team.monthly_budget_usd:
                    return None
                spend_q = await self.db.execute(
                    select(func.coalesce(func.sum(SpendLedger.amount_usd), 0)).where(
                        SpendLedger.team_id == rule.scope_id,
                        SpendLedger.period_month == period_month,
                    )
                )
                spend = float(spend_q.scalar() or 0)
                return max(0.0, float(team.monthly_budget_usd) - spend)

            else:
                return None

        logger.warning("Unknown alert metric '%s' for rule %s", metric, rule.id)
        return None

    def _scope_filter(self, rule: AlertRule, model) -> list:
        """Return SQLAlchemy WHERE clauses to scope a query to the rule's entity."""
        filters = []
        if rule.scope_type == "key" and rule.scope_id:
            filters.append(model.virtual_key_id == rule.scope_id)
        elif rule.scope_type == "team" and rule.scope_id:
            filters.append(model.team_id == rule.scope_id)
        return filters

    # ── Notification dispatch ─────────────────────────────────────────────────

    async def _record_and_notify(
        self,
        rule_id: int | None,
        rule_name: str,
        metric: str,
        actual_value: float,
        threshold_value: float,
        message: str,
        channel: str = "log",
        target: str | None = None,
    ) -> None:
        event = AlertEvent(
            rule_id=rule_id,  # None for ad-hoc budget alerts
            rule_name=rule_name,
            metric=metric,
            actual_value=actual_value,
            threshold_value=threshold_value,
            message=message,
        )
        self.db.add(event)
        await self.db.flush()

        if channel == "log" or not channel:
            logger.warning("ALERT: %s", message)
        elif channel == "webhook" and target:
            await self._send_webhook(target, message)
        elif channel == "slack" and target:
            await self._send_slack(target, message)
        elif channel == "email" and target:
            await self._send_email(target, message, rule_name)
        else:
            # Fallback: always log so alerts are never silently dropped
            logger.warning("ALERT (channel=%s, target=%s): %s", channel, target, message)

    async def _send_webhook(self, url: str, message: str) -> None:
        import httpx
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(url, json={"text": message, "source": "PromptCaliper Gateway"})
        except Exception as exc:
            logger.warning("Webhook delivery failed (%s): %s", url, exc)

    async def _send_slack(self, webhook_url: str, message: str) -> None:
        """Send an alert to a Slack Incoming Webhook URL."""
        import httpx
        payload = {
            "text": f":warning: *PromptCaliper Alert*\n{message}",
        }
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.post(webhook_url, json=payload)
                if resp.status_code != 200:
                    logger.warning(
                        "Slack delivery returned non-200 (%d): %s",
                        resp.status_code, resp.text,
                    )
        except Exception as exc:
            logger.warning("Slack delivery failed (%s): %s", webhook_url, exc)

    async def _send_email(self, to_address: str, message: str, subject: str) -> None:
        """Send an alert email via SMTP using environment configuration."""
        import os
        import smtplib
        from email.mime.text import MIMEText

        smtp_host = os.environ.get("SMTP_HOST", "")
        smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        smtp_user = os.environ.get("SMTP_USER", "")
        smtp_password = os.environ.get("SMTP_PASSWORD", "")
        smtp_from = os.environ.get("SMTP_FROM", smtp_user)

        if not smtp_host:
            logger.info(
                "Email alert suppressed (SMTP_HOST not configured). "
                "To: %s | Subject: %s | Body: %s",
                to_address, subject, message,
            )
            return

        msg = MIMEText(message)
        msg["Subject"] = f"[PromptCaliper Alert] {subject}"
        msg["From"] = smtp_from
        msg["To"] = to_address

        try:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                if smtp_user and smtp_password:
                    server.starttls()
                    server.login(smtp_user, smtp_password)
                server.send_message(msg)
            logger.info("Alert email sent to %s", to_address)
        except Exception as exc:
            logger.warning("Email delivery failed (to=%s): %s", to_address, exc)
