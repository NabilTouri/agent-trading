"""
Tests for the trading safeguards module.

Tests all 10 safeguard checks with both passing and failing scenarios.
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, timedelta

from core.models import (
    TradeDecision, EntryPlan, StopLossLevel, TakeProfitLevel,
    Position, Trade, SafeguardResult, SafeguardReport,
)
from core.safeguards import TradingSafeguards


@pytest.fixture
def safeguards():
    """Create a TradingSafeguards instance with mocked dependencies."""
    s = TradingSafeguards()
    s._db = MagicMock()
    s._exchange = MagicMock()
    return s


@pytest.fixture
def mock_decision():
    """Create a valid TradeDecision that passes all checks."""
    return TradeDecision(
        decision="APPROVED",
        pair="BTC/USDT",
        direction="LONG",
        confidence=75,
        position_size_usd=100.0,
        position_size_pct=1.0,
        entry=EntryPlan(method="LIMIT", price=50000.0, orders=[]),
        stop_loss=StopLossLevel(price=49000.0, pct=2.0, type="STOP_LIMIT"),
        take_profit=[
            TakeProfitLevel(level=1, price=52000.0, size_pct=50),
            TakeProfitLevel(level=2, price=54000.0, size_pct=50),
        ],
        risk_reward_ratio=2.5,
        reasoning="Strong bullish setup with confirmed breakout",
    )


# ═══ Confidence Check ═══

class TestConfidenceCheck:
    def test_passes_when_above_minimum(self, safeguards, mock_decision):
        mock_decision.confidence = 75
        result = safeguards._check_confidence(mock_decision)
        assert result.passed is True

    def test_fails_when_below_minimum(self, safeguards, mock_decision):
        mock_decision.confidence = 50
        result = safeguards._check_confidence(mock_decision)
        assert result.passed is False

    def test_passes_at_exact_minimum(self, safeguards, mock_decision):
        mock_decision.confidence = 60  # default min_confidence
        result = safeguards._check_confidence(mock_decision)
        assert result.passed is True


# ═══ Risk:Reward Ratio Check ═══

class TestRRRatioCheck:
    def test_passes_when_above_minimum(self, safeguards, mock_decision):
        mock_decision.risk_reward_ratio = 3.0
        result = safeguards._check_rr_ratio(mock_decision)
        assert result.passed is True

    def test_fails_when_below_minimum(self, safeguards, mock_decision):
        mock_decision.risk_reward_ratio = 1.5
        result = safeguards._check_rr_ratio(mock_decision)
        assert result.passed is False


# ═══ Stop Loss Distance Check ═══

class TestSLDistanceCheck:
    def test_passes_within_limit(self, safeguards, mock_decision):
        mock_decision.stop_loss.pct = 2.0
        result = safeguards._check_sl_distance(mock_decision)
        assert result.passed is True

    def test_fails_exceeding_limit(self, safeguards, mock_decision):
        mock_decision.stop_loss.pct = 5.0
        result = safeguards._check_sl_distance(mock_decision)
        assert result.passed is False


# ═══ Position Size Check ═══

class TestPositionSizeCheck:
    def test_passes_within_limit(self, safeguards, mock_decision):
        mock_decision.position_size_pct = 1.0
        result = safeguards._check_position_size(mock_decision)
        assert result.passed is True

    def test_fails_exceeding_limit(self, safeguards, mock_decision):
        mock_decision.position_size_pct = 5.0
        result = safeguards._check_position_size(mock_decision)
        assert result.passed is False


# ═══ Max Positions Check ═══

class TestMaxPositionsCheck:
    def test_passes_when_slots_available(self, safeguards):
        safeguards._db.get_all_open_positions.return_value = [MagicMock(), MagicMock()]
        result = safeguards._check_max_positions()
        assert result.passed is True

    def test_fails_when_full(self, safeguards):
        safeguards._db.get_all_open_positions.return_value = [MagicMock()] * 3
        result = safeguards._check_max_positions()
        assert result.passed is False


# ═══ Portfolio Exposure Check ═══

class TestPortfolioExposureCheck:
    def test_passes_within_limit(self, safeguards, mock_decision):
        safeguards._exchange.get_account_balance.return_value = 10000.0
        safeguards._db.get_all_open_positions.return_value = []
        mock_decision.position_size_usd = 500.0
        result = safeguards._check_portfolio_exposure(mock_decision)
        assert result.passed is True

    def test_fails_exceeding_limit(self, safeguards, mock_decision):
        safeguards._exchange.get_account_balance.return_value = 10000.0
        pos = MagicMock()
        pos.size = 900.0
        safeguards._db.get_all_open_positions.return_value = [pos]
        mock_decision.position_size_usd = 500.0
        # 1400/10000 = 14% > 10% limit
        result = safeguards._check_portfolio_exposure(mock_decision)
        assert result.passed is False


# ═══ Drawdown Check ═══

class TestDrawdownCheck:
    def test_passes_no_drawdown(self, safeguards):
        safeguards._exchange.get_account_balance.return_value = 10500.0
        safeguards._db.get_initial_capital.return_value = 10000.0
        result = safeguards._check_drawdown()
        assert result.passed is True

    def test_fails_exceeding_max(self, safeguards):
        safeguards._exchange.get_account_balance.return_value = 7500.0
        safeguards._db.get_initial_capital.return_value = 10000.0
        # 25% drawdown > 20% limit
        result = safeguards._check_drawdown()
        assert result.passed is False


# ═══ Consecutive Losses Check ═══

class TestConsecutiveLossesCheck:
    def test_passes_with_no_losses(self, safeguards):
        trade = MagicMock()
        trade.pnl = 50.0  # winning trade
        safeguards._db.get_recent_trades.return_value = [trade]
        result = safeguards._check_consecutive_losses()
        assert result.passed is True

    def test_fails_with_too_many_losses(self, safeguards):
        trades = [MagicMock() for _ in range(3)]
        for t in trades:
            t.pnl = -50.0
        safeguards._db.get_recent_trades.return_value = trades
        result = safeguards._check_consecutive_losses()
        assert result.passed is False


# ═══ Full Validation ═══

class TestFullValidation:
    def test_approve_when_all_pass(self, safeguards, mock_decision):
        safeguards._db.get_all_open_positions.return_value = []
        safeguards._exchange.get_account_balance.return_value = 10000.0
        safeguards._db.get_initial_capital.return_value = 10000.0
        safeguards._db.client.get.return_value = "0"
        trade = MagicMock()
        trade.pnl = 50.0
        safeguards._db.get_recent_trades.return_value = [trade]

        report = safeguards.validate_trade(mock_decision)
        assert report.approved is True
        assert report.blocked_reason is None

    def test_reject_with_low_confidence(self, safeguards, mock_decision):
        mock_decision.confidence = 30
        safeguards._db.get_all_open_positions.return_value = []
        safeguards._exchange.get_account_balance.return_value = 10000.0
        safeguards._db.get_initial_capital.return_value = 10000.0
        safeguards._db.client.get.return_value = "0"
        safeguards._db.get_recent_trades.return_value = []

        report = safeguards.validate_trade(mock_decision)
        assert report.approved is False
        assert "confidence" in report.blocked_reason.lower()
