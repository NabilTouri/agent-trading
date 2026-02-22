"""
Tests for bot.strategy_loop — StrategyLoop (CrewAI version).
TradingCrew, cost_tracker, safeguards, DB, exchange, and Telegram are mocked.
"""

import pytest
import sys
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime
from core.models import TradeDecision, EntryPlan, StopLossLevel, TakeProfitLevel


def _make_decision(decision="APPROVED", pair="BTC/USDT", direction="LONG",
                   confidence=80, position_size_usd=100.0):
    """Create a sample TradeDecision for testing."""
    return TradeDecision(
        decision=decision,
        pair=pair,
        direction=direction,
        confidence=confidence,
        position_size_usd=position_size_usd,
        position_size_pct=2.0,
        entry=EntryPlan(method="LIMIT", price=50000.0),
        stop_loss=StopLossLevel(price=49000.0, pct=2.0, type="STOP_LIMIT"),
        take_profit=[
            TakeProfitLevel(level=1, price=52000.0, size_pct=50),
            TakeProfitLevel(level=2, price=54000.0, size_pct=50),
        ],
        risk_reward_ratio=2.0,
        reasoning="Strong uptrend with bullish confirmation",
        market_analysis_summary="RSI 55, MACD bullish crossover",
        sentiment_summary="Fear & Greed at 45, neutral sentiment",
    )


class TestStrategyLoop:
    """Tests for StrategyLoop with CrewAI crew mocked."""

    def _build_loop(self):
        """Create a StrategyLoop with mocked dependencies, return (loop, mocks)."""
        from bot.strategy_loop import StrategyLoop
        return StrategyLoop()

    # ── analyze_pair: approved flow ──────────────────────────

    @pytest.mark.asyncio
    @patch("bot.strategy_loop.telegram_notifier")
    @patch("bot.strategy_loop.safeguards")
    @patch("bot.strategy_loop.cost_tracker")
    @patch("bot.strategy_loop.TradingCrew")
    @patch("bot.strategy_loop.exchange")
    @patch("bot.strategy_loop.db")
    @patch("bot.strategy_loop.settings")
    async def test_analyze_pair_approved(self, mock_s, mock_db, mock_ex,
                                         MockCrew, mock_cost, mock_safeguards, mock_tg):
        """Should save a BUY signal when crew approves and safeguards pass."""
        mock_s.strategy_interval_minutes = 30
        mock_s.pairs_list = ["BTC/USDT"]
        mock_s.crew_model = "claude-sonnet-4-20250514"
        mock_s.full_size_confidence = 70

        from bot.strategy_loop import StrategyLoop
        loop = StrategyLoop()

        # Cost budget OK
        mock_cost.check_budget.return_value = True

        # Crew returns APPROVED decision
        decision = _make_decision()
        crew_instance = MockCrew.return_value
        crew_instance.run.return_value = decision
        crew_instance.get_usage_metrics.return_value = {"total_tokens": 5000}

        # Safeguards pass
        report = MagicMock()
        report.approved = True
        mock_safeguards.validate_trade.return_value = report

        mock_tg.send_message = AsyncMock()

        await loop.analyze_pair("BTC/USDT")

        # Signal saved
        mock_db.save_signal.assert_called_once()
        saved_signal = mock_db.save_signal.call_args[0][0]
        assert saved_signal.pair == "BTC/USDT"
        assert saved_signal.action == "BUY"
        assert saved_signal.confidence == 80

    # ── analyze_pair: rejected by crew ───────────────────────

    @pytest.mark.asyncio
    @patch("bot.strategy_loop.telegram_notifier")
    @patch("bot.strategy_loop.safeguards")
    @patch("bot.strategy_loop.cost_tracker")
    @patch("bot.strategy_loop.TradingCrew")
    @patch("bot.strategy_loop.exchange")
    @patch("bot.strategy_loop.db")
    @patch("bot.strategy_loop.settings")
    async def test_analyze_pair_crew_rejected(self, mock_s, mock_db, mock_ex,
                                              MockCrew, mock_cost, mock_safeguards, mock_tg):
        """Should save HOLD signal when crew rejects."""
        mock_s.strategy_interval_minutes = 30
        mock_s.pairs_list = ["BTC/USDT"]
        mock_s.crew_model = "claude-sonnet-4-20250514"
        mock_s.full_size_confidence = 70

        from bot.strategy_loop import StrategyLoop
        loop = StrategyLoop()

        mock_cost.check_budget.return_value = True

        decision = _make_decision(decision="REJECTED", confidence=30)
        crew_instance = MockCrew.return_value
        crew_instance.run.return_value = decision
        crew_instance.get_usage_metrics.return_value = {}

        mock_tg.send_message = AsyncMock()

        await loop.analyze_pair("BTC/USDT")

        mock_db.save_signal.assert_called_once()
        saved_signal = mock_db.save_signal.call_args[0][0]
        assert saved_signal.action == "HOLD"

    # ── analyze_pair: blocked by safeguards ──────────────────

    @pytest.mark.asyncio
    @patch("bot.strategy_loop.telegram_notifier")
    @patch("bot.strategy_loop.safeguards")
    @patch("bot.strategy_loop.cost_tracker")
    @patch("bot.strategy_loop.TradingCrew")
    @patch("bot.strategy_loop.exchange")
    @patch("bot.strategy_loop.db")
    @patch("bot.strategy_loop.settings")
    async def test_analyze_pair_safeguard_blocked(self, mock_s, mock_db, mock_ex,
                                                  MockCrew, mock_cost, mock_safeguards, mock_tg):
        """Should save HOLD when safeguards block an approved decision."""
        mock_s.strategy_interval_minutes = 30
        mock_s.pairs_list = ["BTC/USDT"]
        mock_s.crew_model = "claude-sonnet-4-20250514"
        mock_s.full_size_confidence = 70

        from bot.strategy_loop import StrategyLoop
        loop = StrategyLoop()

        mock_cost.check_budget.return_value = True

        decision = _make_decision()
        crew_instance = MockCrew.return_value
        crew_instance.run.return_value = decision
        crew_instance.get_usage_metrics.return_value = {}

        # Safeguards block
        report = MagicMock()
        report.approved = False
        report.blocked_reason = "Max daily trades exceeded"
        mock_safeguards.validate_trade.return_value = report

        mock_tg.send_message = AsyncMock()

        await loop.analyze_pair("BTC/USDT")

        mock_db.save_signal.assert_called_once()
        saved_signal = mock_db.save_signal.call_args[0][0]
        assert saved_signal.action == "HOLD"
        assert "BLOCKED" in saved_signal.reasoning

    # ── analyze_pair: budget exceeded ────────────────────────

    @pytest.mark.asyncio
    @patch("bot.strategy_loop.telegram_notifier")
    @patch("bot.strategy_loop.safeguards")
    @patch("bot.strategy_loop.cost_tracker")
    @patch("bot.strategy_loop.TradingCrew")
    @patch("bot.strategy_loop.exchange")
    @patch("bot.strategy_loop.db")
    @patch("bot.strategy_loop.settings")
    async def test_analyze_pair_budget_exceeded(self, mock_s, mock_db, mock_ex,
                                                MockCrew, mock_cost, mock_safeguards, mock_tg):
        """Should skip analysis when cost budget is exceeded."""
        mock_s.strategy_interval_minutes = 30
        mock_s.pairs_list = ["BTC/USDT"]
        mock_s.crew_model = "claude-sonnet-4-20250514"
        mock_s.full_size_confidence = 70

        from bot.strategy_loop import StrategyLoop
        loop = StrategyLoop()

        mock_cost.check_budget.return_value = False

        await loop.analyze_pair("BTC/USDT")

        # Crew should NOT be called
        MockCrew.assert_not_called()
        mock_db.save_signal.assert_not_called()

    # ── analyze_pair: crew returns None ──────────────────────

    @pytest.mark.asyncio
    @patch("bot.strategy_loop.telegram_notifier")
    @patch("bot.strategy_loop.safeguards")
    @patch("bot.strategy_loop.cost_tracker")
    @patch("bot.strategy_loop.TradingCrew")
    @patch("bot.strategy_loop.exchange")
    @patch("bot.strategy_loop.db")
    @patch("bot.strategy_loop.settings")
    async def test_analyze_pair_crew_returns_none(self, mock_s, mock_db, mock_ex,
                                                  MockCrew, mock_cost, mock_safeguards, mock_tg):
        """Should handle crew returning None gracefully."""
        mock_s.strategy_interval_minutes = 30
        mock_s.pairs_list = ["BTC/USDT"]
        mock_s.crew_model = "claude-sonnet-4-20250514"
        mock_s.full_size_confidence = 70

        from bot.strategy_loop import StrategyLoop
        loop = StrategyLoop()

        mock_cost.check_budget.return_value = True

        crew_instance = MockCrew.return_value
        crew_instance.run.return_value = None

        await loop.analyze_pair("BTC/USDT")

        mock_db.save_signal.assert_not_called()

    # ── _notify_signal ───────────────────────────────────────

    @pytest.mark.asyncio
    @patch("bot.strategy_loop.telegram_notifier")
    @patch("bot.strategy_loop.safeguards")
    @patch("bot.strategy_loop.cost_tracker")
    @patch("bot.strategy_loop.TradingCrew")
    @patch("bot.strategy_loop.exchange")
    @patch("bot.strategy_loop.db")
    @patch("bot.strategy_loop.settings")
    async def test_notify_signal_buy(self, mock_s, mock_db, mock_ex,
                                     MockCrew, mock_cost, mock_safeguards, mock_tg):
        """Should send Telegram notification with green emoji for BUY."""
        mock_s.strategy_interval_minutes = 30
        mock_s.pairs_list = ["BTC/USDT"]
        mock_s.crew_model = "claude-sonnet-4-20250514"
        mock_s.full_size_confidence = 70

        from bot.strategy_loop import StrategyLoop
        loop = StrategyLoop()

        mock_tg.send_message = AsyncMock()

        from core.models import Signal, ActionType
        signal = Signal(
            pair="ETH/USDT",
            action=ActionType.BUY,
            confidence=85.0,
            reasoning="strong buy signal",
            agent_votes={"market_analysis": "uptrend", "trading_ops": "APPROVED"},
            market_data={"price": 3000.0},
        )
        decision = _make_decision(pair="ETH/USDT")

        await loop._notify_signal(signal, decision)

        mock_tg.send_message.assert_called_once()
        msg = mock_tg.send_message.call_args[0][0]
        assert "🟢" in msg
        assert "ETH/USDT" in msg

    @pytest.mark.asyncio
    @patch("bot.strategy_loop.telegram_notifier")
    @patch("bot.strategy_loop.safeguards")
    @patch("bot.strategy_loop.cost_tracker")
    @patch("bot.strategy_loop.TradingCrew")
    @patch("bot.strategy_loop.exchange")
    @patch("bot.strategy_loop.db")
    @patch("bot.strategy_loop.settings")
    async def test_notify_signal_sell(self, mock_s, mock_db, mock_ex,
                                      MockCrew, mock_cost, mock_safeguards, mock_tg):
        """Should send Telegram notification with red emoji for SELL."""
        mock_s.strategy_interval_minutes = 30
        mock_s.pairs_list = ["BTC/USDT"]
        mock_s.crew_model = "claude-sonnet-4-20250514"
        mock_s.full_size_confidence = 70

        from bot.strategy_loop import StrategyLoop
        loop = StrategyLoop()

        mock_tg.send_message = AsyncMock()

        from core.models import Signal, ActionType
        signal = Signal(
            pair="BTC/USDT",
            action=ActionType.SELL,
            confidence=78.0,
            reasoning="short signal",
            agent_votes={},
            market_data={},
        )
        decision = _make_decision(direction="SHORT")

        await loop._notify_signal(signal, decision)

        mock_tg.send_message.assert_called_once()
        msg = mock_tg.send_message.call_args[0][0]
        assert "🔴" in msg


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
