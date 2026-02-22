"""
Tests for the cost tracker module.

Tests token usage logging, daily/monthly cost calculation,
budget enforcement, and alerting thresholds.
"""

import pytest
import json
from unittest.mock import MagicMock, patch
from datetime import datetime, date

from core.cost_tracker import CostTracker, UsageRecord, INPUT_COST_PER_MTOK, OUTPUT_COST_PER_MTOK


@pytest.fixture
def tracker():
    """Create a CostTracker with mocked Redis."""
    t = CostTracker()
    t._db = MagicMock()
    t._alert_sent = {}
    return t


# ═══ UsageRecord ═══

class TestUsageRecord:
    def test_calculate_cost(self):
        record = UsageRecord(
            timestamp=datetime.now(),
            input_tokens=1_000_000,
            output_tokens=100_000,
        )
        cost = record.calculate_cost()
        expected = (1_000_000 / 1_000_000 * INPUT_COST_PER_MTOK) + \
                   (100_000 / 1_000_000 * OUTPUT_COST_PER_MTOK)
        assert abs(cost - expected) < 0.001

    def test_calculate_cost_with_cached(self):
        record = UsageRecord(
            timestamp=datetime.now(),
            input_tokens=500_000,
            output_tokens=50_000,
            cached_input_tokens=500_000,
        )
        cost = record.calculate_cost()
        assert cost > 0
        assert record.cost_usd == cost


# ═══ Log Usage ═══

class TestLogUsage:
    def test_log_usage_stores_in_redis(self, tracker):
        usage = {
            "prompt_tokens": 5000,
            "completion_tokens": 1000,
            "cached_tokens": 0,
        }

        record = tracker.log_usage(usage, pair="BTC/USDT")
        assert record.input_tokens == 5000
        assert record.output_tokens == 1000
        assert record.cost_usd > 0
        assert record.pair == "BTC/USDT"

        # Verify Redis rpush was called
        tracker._db.client.rpush.assert_called_once()

    def test_log_usage_handles_redis_error(self, tracker):
        tracker._db.client.rpush.side_effect = Exception("Redis down")

        usage = {"prompt_tokens": 1000, "completion_tokens": 100}
        record = tracker.log_usage(usage)

        # Should not raise, just log error
        assert record.cost_usd > 0


# ═══ Daily/Monthly Cost ═══

class TestCostAggregation:
    def test_get_daily_cost(self, tracker):
        records = [
            json.dumps({"cost_usd": 0.5}),
            json.dumps({"cost_usd": 0.3}),
        ]
        tracker._db.client.lrange.return_value = records
        cost = tracker.get_daily_cost()
        assert cost == 0.8

    def test_get_daily_cost_empty(self, tracker):
        tracker._db.client.lrange.return_value = []
        cost = tracker.get_daily_cost()
        assert cost == 0.0


# ═══ Budget Check ═══

class TestBudgetCheck:
    @patch.object(CostTracker, 'get_daily_cost', return_value=1.0)
    @patch.object(CostTracker, 'get_monthly_cost', return_value=10.0)
    def test_within_budget(self, mock_monthly, mock_daily, tracker):
        assert tracker.check_budget() is True

    @patch.object(CostTracker, 'get_daily_cost', return_value=6.0)
    @patch.object(CostTracker, 'get_monthly_cost', return_value=10.0)
    def test_daily_limit_exceeded(self, mock_monthly, mock_daily, tracker):
        assert tracker.check_budget() is False


# ═══ Cost Summary ═══

class TestCostSummary:
    @patch.object(CostTracker, 'get_daily_cost', return_value=2.5)
    @patch.object(CostTracker, 'get_monthly_cost', return_value=50.0)
    @patch.object(CostTracker, 'check_budget', return_value=True)
    def test_summary_structure(self, mock_budget, mock_monthly, mock_daily, tracker):
        summary = tracker.get_cost_summary()
        assert "daily_cost_usd" in summary
        assert "monthly_cost_usd" in summary
        assert "budget_ok" in summary
        assert summary["daily_cost_usd"] == 2.5
        assert summary["budget_ok"] is True
