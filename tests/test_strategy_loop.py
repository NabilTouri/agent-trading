"""
Tests for bot.strategy_loop — StrategyLoop.
All agents, pipeline, DB, and telegram are mocked.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime


class TestStrategyLoop:
    """Tests for StrategyLoop with mocked dependencies."""

    # ── _calculate_drawdown ──────────────────────────────────

    def test_drawdown_no_loss(self):
        """Drawdown should be 0 when capital >= initial."""
        with patch("bot.strategy_loop.settings") as mock_s, \
             patch("bot.strategy_loop.db") as mock_db, \
             patch("bot.strategy_loop.exchange") as mock_ex, \
             patch("bot.strategy_loop.MarketAnalysisAgent"), \
             patch("bot.strategy_loop.RiskManagementAgent"), \
             patch("bot.strategy_loop.OrchestratorAgent"), \
             patch("bot.strategy_loop.DataPipeline"), \
             patch("bot.strategy_loop.telegram_notifier"):
            mock_s.strategy_interval_minutes = 30
            mock_db.get_initial_capital.return_value = 3000.0
            mock_ex.get_account_balance.return_value = 3500.0

            from bot.strategy_loop import StrategyLoop
            loop = StrategyLoop()
            assert loop._calculate_drawdown() == 0.0

    def test_drawdown_with_loss(self):
        """Drawdown should be % loss from initial capital."""
        with patch("bot.strategy_loop.settings") as mock_s, \
             patch("bot.strategy_loop.db") as mock_db, \
             patch("bot.strategy_loop.exchange") as mock_ex, \
             patch("bot.strategy_loop.MarketAnalysisAgent"), \
             patch("bot.strategy_loop.RiskManagementAgent"), \
             patch("bot.strategy_loop.OrchestratorAgent"), \
             patch("bot.strategy_loop.DataPipeline"), \
             patch("bot.strategy_loop.telegram_notifier"):
            mock_s.strategy_interval_minutes = 30
            mock_db.get_initial_capital.return_value = 3000.0
            mock_ex.get_account_balance.return_value = 2700.0  # 10% loss

            from bot.strategy_loop import StrategyLoop
            loop = StrategyLoop()
            dd = loop._calculate_drawdown()
            assert abs(dd - 10.0) < 0.01

    # ── analyze_pair ─────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_analyze_pair_full_flow(self):
        """Should run market → risk → orchestrator → save signal."""
        with patch("bot.strategy_loop.settings") as mock_s, \
             patch("bot.strategy_loop.db") as mock_db, \
             patch("bot.strategy_loop.exchange") as mock_ex, \
             patch("bot.strategy_loop.MarketAnalysisAgent") as MockMA, \
             patch("bot.strategy_loop.RiskManagementAgent") as MockRM, \
             patch("bot.strategy_loop.OrchestratorAgent") as MockOrch, \
             patch("bot.strategy_loop.DataPipeline") as MockDP, \
             patch("bot.strategy_loop.telegram_notifier") as mock_tg:

            mock_s.strategy_interval_minutes = 30

            # Pipeline mock
            mock_dp = MockDP.return_value
            mock_dp.fetch_market_data = AsyncMock(return_value={
                "pair": "BTC/USDT",
                "current_price": 50000.0,
                "indicators": {"rsi": 55.0},
            })

            # Agent mocks
            MockMA.return_value.analyze.return_value = {
                "action": "BUY", "confidence": 80, "reasoning": "uptrend"
            }
            MockRM.return_value.analyze.return_value = {
                "action": "APPROVE", "confidence": 75,
                "stop_loss": 49000, "take_profit": 52000, "position_size_usd": 100
            }
            MockOrch.return_value.make_decision.return_value = {
                "final_action": "BUY", "confidence": 75,
                "reasoning": "all agree", "risk_level": "MEDIUM"
            }

            # DB mocks
            mock_db.get_initial_capital.return_value = 3000.0
            mock_ex.get_account_balance.return_value = 3000.0
            mock_db.get_all_open_positions.return_value = []
            mock_db.calculate_metrics.return_value = {
                "win_rate": 60.0, "avg_profit": 5.0, "avg_loss": 3.0
            }

            mock_tg.send_message = AsyncMock()

            from bot.strategy_loop import StrategyLoop
            loop = StrategyLoop()
            await loop.analyze_pair("BTC/USDT")

            # Should save signal
            mock_db.save_signal.assert_called_once()
            saved = mock_db.save_signal.call_args[0][0]
            assert saved.pair == "BTC/USDT"
            assert saved.action == "BUY"

    @pytest.mark.asyncio
    async def test_analyze_pair_hold_no_notify(self):
        """HOLD signal should NOT trigger Telegram notification."""
        with patch("bot.strategy_loop.settings") as mock_s, \
             patch("bot.strategy_loop.db") as mock_db, \
             patch("bot.strategy_loop.exchange") as mock_ex, \
             patch("bot.strategy_loop.MarketAnalysisAgent") as MockMA, \
             patch("bot.strategy_loop.RiskManagementAgent") as MockRM, \
             patch("bot.strategy_loop.OrchestratorAgent") as MockOrch, \
             patch("bot.strategy_loop.DataPipeline") as MockDP, \
             patch("bot.strategy_loop.telegram_notifier") as mock_tg:

            mock_s.strategy_interval_minutes = 30

            mock_dp = MockDP.return_value
            mock_dp.fetch_market_data = AsyncMock(return_value={
                "pair": "BTC/USDT",
                "current_price": 50000.0,
                "indicators": {"rsi": 50.0},
            })

            MockMA.return_value.analyze.return_value = {
                "action": "HOLD", "confidence": 40
            }
            MockRM.return_value.analyze.return_value = {
                "action": "REJECT", "confidence": 30,
                "stop_loss": 0, "take_profit": 0, "position_size_usd": 0
            }
            MockOrch.return_value.make_decision.return_value = {
                "final_action": "HOLD", "confidence": 30,
                "reasoning": "no signal", "risk_level": "HIGH"
            }

            mock_db.get_initial_capital.return_value = 3000.0
            mock_ex.get_account_balance.return_value = 3000.0
            mock_db.get_all_open_positions.return_value = []
            mock_db.calculate_metrics.return_value = {
                "win_rate": 50.0, "avg_profit": 0.0, "avg_loss": 0.0
            }

            mock_tg.send_message = AsyncMock()

            from bot.strategy_loop import StrategyLoop
            loop = StrategyLoop()
            await loop.analyze_pair("BTC/USDT")

            mock_tg.send_message.assert_not_called()

    # ── _notify_signal ───────────────────────────────────────

    @pytest.mark.asyncio
    async def test_notify_signal_buy(self):
        """Should send buy notification with green emoji."""
        with patch("bot.strategy_loop.settings") as mock_s, \
             patch("bot.strategy_loop.db"), \
             patch("bot.strategy_loop.exchange"), \
             patch("bot.strategy_loop.MarketAnalysisAgent"), \
             patch("bot.strategy_loop.RiskManagementAgent"), \
             patch("bot.strategy_loop.OrchestratorAgent"), \
             patch("bot.strategy_loop.DataPipeline"), \
             patch("bot.strategy_loop.telegram_notifier") as mock_tg:

            mock_s.strategy_interval_minutes = 30
            mock_tg.send_message = AsyncMock()

            from bot.strategy_loop import StrategyLoop
            from core.models import Signal, ActionType

            loop = StrategyLoop()

            signal = Signal(
                pair="ETH/USDT",
                action=ActionType.BUY,
                confidence=85.0,
                reasoning="strong buy",
                agent_votes={"market_analysis": "BUY", "risk_management": "APPROVE"},
                market_data={"price": 3000.0},
            )

            await loop._notify_signal(signal)
            mock_tg.send_message.assert_called_once()
            msg = mock_tg.send_message.call_args[0][0]
            assert "🟢" in msg
            assert "ETH/USDT" in msg
