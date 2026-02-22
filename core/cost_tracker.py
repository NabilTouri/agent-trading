"""
Cost tracking and budget enforcement for Claude API usage.

Tracks token usage per analysis cycle and enforces daily/monthly limits.
Sends Telegram alerts at 70%, 90%, and 100% of daily budget.
"""

import json
from datetime import datetime, date
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger

from core.config import settings


# Claude Sonnet 4 pricing (per million tokens)
INPUT_COST_PER_MTOK: float = 3.00
OUTPUT_COST_PER_MTOK: float = 15.00
CACHED_INPUT_COST_PER_MTOK: float = 0.30


@dataclass
class UsageRecord:
    """Single API usage record."""
    timestamp: datetime
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    pair: str = ""
    cost_usd: float = 0.0

    def calculate_cost(self) -> float:
        """Calculate cost in USD for this record."""
        input_cost = (self.input_tokens / 1_000_000) * INPUT_COST_PER_MTOK
        output_cost = (self.output_tokens / 1_000_000) * OUTPUT_COST_PER_MTOK
        cached_cost = (self.cached_input_tokens / 1_000_000) * CACHED_INPUT_COST_PER_MTOK
        self.cost_usd = input_cost + output_cost + cached_cost
        return self.cost_usd


class CostTracker:
    """
    Track API token usage and enforce cost limits.
    
    Stores daily/monthly usage in Redis. Alerts via Telegram at thresholds.
    """

    def __init__(self) -> None:
        # Lazy import to avoid circular dependency at module load
        self._db: Optional[Any] = None
        self._alert_sent: Dict[str, bool] = {}  # track which alerts fired today

    @property
    def db(self) -> Any:
        """Lazy-load database to avoid import-time Redis connection."""
        if self._db is None:
            from core.database import db
            self._db = db
        return self._db

    def log_usage(self, usage_metrics: Dict[str, Any], pair: str = "") -> UsageRecord:
        """
        Log token usage from a CrewAI kickoff.
        
        Args:
            usage_metrics: Dict with 'total_tokens', 'prompt_tokens', 'completion_tokens'
                          as returned by crew.usage_metrics
            pair: Trading pair this analysis was for
        
        Returns:
            UsageRecord with calculated cost
        """
        record = UsageRecord(
            timestamp=datetime.now(),
            input_tokens=usage_metrics.get("prompt_tokens", 0),
            output_tokens=usage_metrics.get("completion_tokens", 0),
            cached_input_tokens=usage_metrics.get("cached_tokens", 0),
            pair=pair,
        )
        record.calculate_cost()

        # Store in Redis
        today = date.today().isoformat()
        key = f"costs:daily:{today}"
        record_json = json.dumps({
            "timestamp": record.timestamp.isoformat(),
            "input_tokens": record.input_tokens,
            "output_tokens": record.output_tokens,
            "cached_input_tokens": record.cached_input_tokens,
            "pair": record.pair,
            "cost_usd": record.cost_usd,
        })

        try:
            self.db.client.rpush(key, record_json)
            self.db.client.expire(key, 60 * 60 * 24 * 30)  # Keep 30 days
        except Exception as e:
            logger.error(f"Failed to store cost record: {e}")

        logger.info(
            f"💰 API cost: ${record.cost_usd:.4f} "
            f"(in:{record.input_tokens} out:{record.output_tokens} "
            f"cached:{record.cached_input_tokens})"
        )

        # Check alert thresholds
        self._check_alerts(today)

        return record

    def get_daily_cost(self, day: Optional[str] = None) -> float:
        """Get total cost for a given day (default: today)."""
        if day is None:
            day = date.today().isoformat()

        key = f"costs:daily:{day}"
        try:
            records = self.db.client.lrange(key, 0, -1)
            total = sum(json.loads(r).get("cost_usd", 0) for r in records)
            return round(total, 4)
        except Exception as e:
            logger.error(f"Failed to read daily cost: {e}")
            return 0.0

    def get_monthly_cost(self) -> float:
        """Get total cost for the current month."""
        today = date.today()
        total = 0.0

        for day_num in range(1, today.day + 1):
            day_str = date(today.year, today.month, day_num).isoformat()
            total += self.get_daily_cost(day_str)

        return round(total, 4)

    def check_budget(self) -> bool:
        """
        Check if we are within budget to run another analysis.
        
        Returns:
            True if budget allows, False if daily limit exceeded.
        """
        daily_cost = self.get_daily_cost()

        if daily_cost >= settings.daily_cost_limit_usd:
            logger.warning(
                f"🚫 Daily cost limit reached: ${daily_cost:.2f} / "
                f"${settings.daily_cost_limit_usd:.2f}"
            )
            return False

        monthly_cost = self.get_monthly_cost()
        if monthly_cost >= settings.monthly_cost_limit_usd:
            logger.warning(
                f"🚫 Monthly cost limit reached: ${monthly_cost:.2f} / "
                f"${settings.monthly_cost_limit_usd:.2f}"
            )
            return False

        return True

    def get_cost_summary(self) -> Dict[str, Any]:
        """Get cost summary for API/monitoring."""
        daily = self.get_daily_cost()
        monthly = self.get_monthly_cost()

        return {
            "daily_cost_usd": daily,
            "daily_limit_usd": settings.daily_cost_limit_usd,
            "daily_utilization_pct": round(
                (daily / settings.daily_cost_limit_usd) * 100, 1
            ) if settings.daily_cost_limit_usd > 0 else 0,
            "monthly_cost_usd": monthly,
            "monthly_limit_usd": settings.monthly_cost_limit_usd,
            "monthly_utilization_pct": round(
                (monthly / settings.monthly_cost_limit_usd) * 100, 1
            ) if settings.monthly_cost_limit_usd > 0 else 0,
            "budget_ok": self.check_budget(),
        }

    def _check_alerts(self, today: str) -> None:
        """Send Telegram alerts at 70%, 90%, 100% of daily limit."""
        daily_cost = self.get_daily_cost(today)
        pct = (daily_cost / settings.daily_cost_limit_usd * 100) if settings.daily_cost_limit_usd > 0 else 0

        thresholds = [
            (70, "⚠️"),
            (90, "🔶"),
            (100, "🚫"),
        ]

        for threshold, emoji in thresholds:
            alert_key = f"{today}:{threshold}"
            if pct >= threshold and alert_key not in self._alert_sent:
                self._alert_sent[alert_key] = True
                self._send_cost_alert(emoji, threshold, daily_cost)

    def _send_cost_alert(self, emoji: str, threshold: int, cost: float) -> None:
        """Send cost alert via Telegram (fire-and-forget)."""
        try:
            from services.telegram_bot import telegram_notifier
            import asyncio

            message = (
                f"{emoji} <b>Cost Alert: {threshold}% of daily limit</b>\n\n"
                f"Daily spend: ${cost:.2f} / ${settings.daily_cost_limit_usd:.2f}\n"
                f"Monthly: ${self.get_monthly_cost():.2f} / ${settings.monthly_cost_limit_usd:.2f}"
            )
            telegram_notifier.send_message_sync(message)
        except Exception as e:
            logger.error(f"Failed to send cost alert: {e}")


# Singleton instance
cost_tracker = CostTracker()
