"""
Tests for bot.execution_loop — ExecutionLoop.
All external services (DB, exchange, telegram) are mocked.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timedelta
from core.models import Signal, Position, ActionType


class TestExecutionLoop:
    """Tests for ExecutionLoop with mocked dependencies."""

    def _make_loop(self):
        """Create an ExecutionLoop with mocked settings."""
        with patch("bot.execution_loop.settings") as mock_s, \
             patch("bot.execution_loop.db") as mock_db, \
             patch("bot.execution_loop.exchange") as mock_ex, \
             patch("bot.execution_loop.telegram_notifier") as mock_tg:
            mock_s.execution_interval_seconds = 10
            mock_s.pairs_list = ["BTC/USDT"]
            mock_s.max_positions = 3

            from bot.execution_loop import ExecutionLoop
            loop = ExecutionLoop()

        return loop

    # ── check_signals ────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_check_signals_no_signal(self):
        """Should skip when no signal exists."""
        with patch("bot.execution_loop.settings") as mock_s, \
             patch("bot.execution_loop.db") as mock_db, \
             patch("bot.execution_loop.exchange"), \
             patch("bot.execution_loop.telegram_notifier"):
            mock_s.execution_interval_seconds = 10
            mock_s.pairs_list = ["BTC/USDT"]

            from bot.execution_loop import ExecutionLoop
            loop = ExecutionLoop()
            mock_db.get_latest_signal.return_value = None
            await loop.check_signals()
            # No error, just skipped

    @pytest.mark.asyncio
    async def test_check_signals_old_signal(self):
        """Should ignore signals older than 5 minutes."""
        with patch("bot.execution_loop.settings") as mock_s, \
             patch("bot.execution_loop.db") as mock_db, \
             patch("bot.execution_loop.exchange"), \
             patch("bot.execution_loop.telegram_notifier"):
            mock_s.execution_interval_seconds = 10
            mock_s.pairs_list = ["BTC/USDT"]
            mock_s.max_positions = 3

            from bot.execution_loop import ExecutionLoop
            loop = ExecutionLoop()

            old_signal = Signal(
                pair="BTC/USDT",
                action=ActionType.BUY,
                confidence=80.0,
                reasoning="test",
                agent_votes={},
                market_data={"position_size": 100, "stop_loss": 49000, "take_profit": 52000},
                timestamp=datetime.now() - timedelta(minutes=10),
            )
            mock_db.get_latest_signal.return_value = old_signal
            await loop.check_signals()
            # Signal was too old, no execution

    @pytest.mark.asyncio
    async def test_check_signals_low_confidence(self):
        """Should skip signals with confidence < 60."""
        with patch("bot.execution_loop.settings") as mock_s, \
             patch("bot.execution_loop.db") as mock_db, \
             patch("bot.execution_loop.exchange"), \
             patch("bot.execution_loop.telegram_notifier"):
            mock_s.execution_interval_seconds = 10
            mock_s.pairs_list = ["BTC/USDT"]
            mock_s.max_positions = 3

            from bot.execution_loop import ExecutionLoop
            loop = ExecutionLoop()

            weak_signal = Signal(
                pair="BTC/USDT",
                action=ActionType.BUY,
                confidence=30.0,
                reasoning="low conf",
                agent_votes={},
                market_data={},
            )
            mock_db.get_latest_signal.return_value = weak_signal
            await loop.check_signals()

    @pytest.mark.asyncio
    async def test_check_signals_hold(self):
        """Should skip HOLD signals."""
        with patch("bot.execution_loop.settings") as mock_s, \
             patch("bot.execution_loop.db") as mock_db, \
             patch("bot.execution_loop.exchange"), \
             patch("bot.execution_loop.telegram_notifier"):
            mock_s.execution_interval_seconds = 10
            mock_s.pairs_list = ["BTC/USDT"]
            mock_s.max_positions = 3

            from bot.execution_loop import ExecutionLoop
            loop = ExecutionLoop()

            hold_signal = Signal(
                pair="BTC/USDT",
                action=ActionType.HOLD,
                confidence=90.0,
                reasoning="hold",
                agent_votes={},
                market_data={},
            )
            mock_db.get_latest_signal.return_value = hold_signal
            await loop.check_signals()

    # ── execute_signal ───────────────────────────────────────

    @pytest.mark.asyncio
    async def test_execute_signal_success(self):
        """Should open a position when signal is valid."""
        with patch("bot.execution_loop.settings") as mock_s, \
             patch("bot.execution_loop.db") as mock_db, \
             patch("bot.execution_loop.exchange") as mock_ex, \
             patch("bot.execution_loop.telegram_notifier") as mock_tg:
            mock_s.execution_interval_seconds = 10
            mock_tg.send_message = AsyncMock()

            from bot.execution_loop import ExecutionLoop
            loop = ExecutionLoop()

            signal = Signal(
                pair="BTC/USDT",
                action=ActionType.BUY,
                confidence=85.0,
                reasoning="strong buy",
                agent_votes={"market": "BUY"},
                market_data={"position_size": 100, "stop_loss": 49000, "take_profit": 52000},
            )
            mock_ex.get_current_price.return_value = 50000.0
            mock_ex.place_market_order.return_value = {"orderId": 123}

            await loop.execute_signal(signal)

            mock_db.save_position.assert_called_once()
            mock_tg.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_signal_zero_size(self):
        """Should abort when position_size is 0."""
        with patch("bot.execution_loop.settings") as mock_s, \
             patch("bot.execution_loop.db") as mock_db, \
             patch("bot.execution_loop.exchange") as mock_ex, \
             patch("bot.execution_loop.telegram_notifier"):
            mock_s.execution_interval_seconds = 10

            from bot.execution_loop import ExecutionLoop
            loop = ExecutionLoop()

            signal = Signal(
                pair="BTC/USDT",
                action=ActionType.BUY,
                confidence=85.0,
                reasoning="buy",
                agent_votes={},
                market_data={"position_size": 0, "stop_loss": 49000},
            )
            mock_ex.get_current_price.return_value = 50000.0

            await loop.execute_signal(signal)
            mock_db.save_position.assert_not_called()

    # ── close_position ───────────────────────────────────────

    @pytest.mark.asyncio
    async def test_close_position_long_profit(self):
        """Should close LONG position with profit and update capital."""
        with patch("bot.execution_loop.settings") as mock_s, \
             patch("bot.execution_loop.db") as mock_db, \
             patch("bot.execution_loop.exchange") as mock_ex, \
             patch("bot.execution_loop.telegram_notifier") as mock_tg:
            mock_s.execution_interval_seconds = 10
            mock_tg.send_message = AsyncMock()

            from bot.execution_loop import ExecutionLoop
            loop = ExecutionLoop()

            pos = Position(
                pair="BTC/USDT",
                side="LONG",
                entry_price=50000.0,
                size=100.0,
                quantity=0.002,
                stop_loss=49000.0,
                signal_id="sig_1",
            )
            mock_ex.close_position.return_value = True
            mock_db.get_current_capital.return_value = 3000.0

            await loop.close_position(pos, exit_price=51000.0, reason="TP")

            mock_db.save_trade.assert_called_once()
            mock_db.close_position.assert_called_once_with(pos.position_id)
            mock_db.update_capital.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_position_short_profit(self):
        """Should calculate PnL correctly for SHORT positions."""
        with patch("bot.execution_loop.settings") as mock_s, \
             patch("bot.execution_loop.db") as mock_db, \
             patch("bot.execution_loop.exchange") as mock_ex, \
             patch("bot.execution_loop.telegram_notifier") as mock_tg:
            mock_s.execution_interval_seconds = 10
            mock_tg.send_message = AsyncMock()

            from bot.execution_loop import ExecutionLoop
            loop = ExecutionLoop()

            pos = Position(
                pair="BTC/USDT",
                side="SHORT",
                entry_price=50000.0,
                size=100.0,
                quantity=0.002,
                stop_loss=51000.0,
                signal_id="sig_1",
            )
            mock_ex.close_position.return_value = True
            mock_db.get_current_capital.return_value = 3000.0

            await loop.close_position(pos, exit_price=49000.0, reason="TP")

            # Verify trade was saved
            saved_trade = mock_db.save_trade.call_args[0][0]
            assert saved_trade.pnl > 0  # SHORT: entry > exit = profit

    # ── monitor_positions ────────────────────────────────────

    @pytest.mark.asyncio
    async def test_monitor_positions_stop_loss_long(self):
        """Should close LONG when price drops below stop_loss."""
        with patch("bot.execution_loop.settings") as mock_s, \
             patch("bot.execution_loop.db") as mock_db, \
             patch("bot.execution_loop.exchange") as mock_ex, \
             patch("bot.execution_loop.telegram_notifier") as mock_tg:
            mock_s.execution_interval_seconds = 10
            mock_tg.send_message = AsyncMock()

            from bot.execution_loop import ExecutionLoop
            loop = ExecutionLoop()

            pos = Position(
                pair="BTC/USDT",
                side="LONG",
                entry_price=50000.0,
                size=100.0,
                quantity=0.002,
                stop_loss=49000.0,
                take_profit=52000.0,
                signal_id="sig_1",
            )
            mock_db.get_all_open_positions.return_value = [pos]
            mock_ex.get_current_price.return_value = 48500.0  # below SL
            mock_ex.close_position.return_value = True
            mock_db.get_current_capital.return_value = 3000.0
            mock_db.get_latest_signal.return_value = None

            await loop.monitor_positions()

            mock_db.save_trade.assert_called_once()

    @pytest.mark.asyncio
    async def test_monitor_positions_take_profit_long(self):
        """Should close LONG when price hits take_profit."""
        with patch("bot.execution_loop.settings") as mock_s, \
             patch("bot.execution_loop.db") as mock_db, \
             patch("bot.execution_loop.exchange") as mock_ex, \
             patch("bot.execution_loop.telegram_notifier") as mock_tg:
            mock_s.execution_interval_seconds = 10
            mock_tg.send_message = AsyncMock()

            from bot.execution_loop import ExecutionLoop
            loop = ExecutionLoop()

            pos = Position(
                pair="BTC/USDT",
                side="LONG",
                entry_price=50000.0,
                size=100.0,
                quantity=0.002,
                stop_loss=49000.0,
                take_profit=52000.0,
                signal_id="sig_1",
            )
            mock_db.get_all_open_positions.return_value = [pos]
            mock_ex.get_current_price.return_value = 52500.0  # above TP
            mock_ex.close_position.return_value = True
            mock_db.get_current_capital.return_value = 3000.0
            mock_db.get_latest_signal.return_value = None

            await loop.monitor_positions()

            mock_db.save_trade.assert_called_once()
