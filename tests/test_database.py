"""
Tests for core.database — RedisManager.
All Redis calls are mocked.
"""

import pytest
import json
from unittest.mock import MagicMock, patch
from datetime import datetime
from core.models import Signal, Position, Trade, ActionType


class TestRedisManager:
    """Tests for RedisManager with mocked Redis client."""

    def _make_db(self):
        """Create a RedisManager with a mocked Redis client."""
        from core.database import RedisManager

        with patch.object(RedisManager, "__init__", lambda self: None):
            mgr = RedisManager()
            mgr.client = MagicMock()
            mgr.client.ping.return_value = True
        return mgr

    # ── Signals ──────────────────────────────────────────────

    def test_save_signal(self):
        mgr = self._make_db()
        sig = Signal(
            pair="BTC/USDT",
            action=ActionType.BUY,
            confidence=80.0,
            reasoning="test",
            agent_votes={"m": "BUY"},
            market_data={"price": 50000},
        )
        mgr.save_signal(sig)
        mgr.client.lpush.assert_called_once()
        mgr.client.ltrim.assert_called_once_with("signals:BTC/USDT", 0, 99)

    def test_get_latest_signal_found(self):
        mgr = self._make_db()
        sig = Signal(
            pair="BTC/USDT",
            action=ActionType.BUY,
            confidence=80.0,
            reasoning="test",
            agent_votes={},
            market_data={},
        )
        mgr.client.lindex.return_value = sig.model_dump_json()
        result = mgr.get_latest_signal("BTC/USDT")
        assert result is not None
        assert result.action == ActionType.BUY

    def test_get_latest_signal_not_found(self):
        mgr = self._make_db()
        mgr.client.lindex.return_value = None
        assert mgr.get_latest_signal("BTC/USDT") is None

    def test_get_signals_history(self):
        mgr = self._make_db()
        sig = Signal(
            pair="BTC/USDT",
            action=ActionType.SELL,
            confidence=60.0,
            reasoning="r",
            agent_votes={},
            market_data={},
        )
        mgr.client.lrange.return_value = [sig.model_dump_json()] * 3
        result = mgr.get_signals_history("BTC/USDT", limit=5)
        assert len(result) == 3
        assert all(s.action == ActionType.SELL for s in result)

    # ── Positions ────────────────────────────────────────────

    def test_save_and_get_position(self):
        mgr = self._make_db()
        pos = Position(
            pair="ETH/USDT",
            side="LONG",
            entry_price=3000.0,
            size=100.0,
            quantity=0.033,
            stop_loss=2900.0,
            signal_id="sig_1",
        )

        mgr.save_position(pos)
        mgr.client.setex.assert_called_once()
        mgr.client.sadd.assert_called_with("positions:active", pos.position_id)

        # Get position
        mgr.client.get.return_value = pos.model_dump_json()
        result = mgr.get_position(pos.position_id)
        assert result is not None
        assert result.pair == "ETH/USDT"

    def test_get_all_open_positions(self):
        mgr = self._make_db()
        pos = Position(
            pair="BTC/USDT",
            side="LONG",
            entry_price=50000.0,
            size=100.0,
            quantity=0.002,
            stop_loss=49000.0,
            signal_id="sig_1",
        )
        mgr.client.smembers.return_value = {pos.position_id}
        mgr.client.get.return_value = pos.model_dump_json()
        result = mgr.get_all_open_positions()
        assert len(result) == 1

    def test_close_position(self):
        mgr = self._make_db()
        mgr.close_position("pos_123")
        mgr.client.srem.assert_called_with("positions:active", "pos_123")
        mgr.client.delete.assert_called_with("positions:open:pos_123")

    # ── Trades ───────────────────────────────────────────────

    def test_save_trade(self):
        mgr = self._make_db()
        trade = Trade(
            position_id="pos_1",
            pair="BTC/USDT",
            side="LONG",
            entry_price=50000.0,
            exit_price=51000.0,
            size=100.0,
            quantity=0.002,
            pnl=2.0,
            pnl_percent=2.0,
            fees=0.08,
            opened_at=datetime.now(),
            duration_minutes=30,
            exit_reason="TP",
        )
        mgr.save_trade(trade)
        mgr.client.lpush.assert_called_once()
        mgr.client.ltrim.assert_called_once_with("trades:history:BTC/USDT", 0, 499)

    def test_get_trades_history_by_pair(self):
        mgr = self._make_db()
        trade = Trade(
            position_id="pos_1",
            pair="BTC/USDT",
            side="LONG",
            entry_price=50000.0,
            exit_price=51000.0,
            size=100.0,
            quantity=0.002,
            pnl=2.0,
            pnl_percent=2.0,
            fees=0.08,
            opened_at=datetime.now(),
            duration_minutes=30,
            exit_reason="TP",
        )
        mgr.client.lrange.return_value = [trade.model_dump_json()]
        result = mgr.get_trades_history(pair="BTC/USDT")
        assert len(result) == 1

    # ── Candles ───────────────────────────────────────────────

    def test_save_candles(self):
        mgr = self._make_db()
        pipeline = MagicMock()
        mgr.client.pipeline.return_value = pipeline
        candles = [{"open": 50000, "close": 50100}]
        mgr.save_candles("BTC/USDT", "1h", candles)
        pipeline.execute.assert_called_once()

    def test_get_candles(self):
        mgr = self._make_db()
        mgr.client.lrange.return_value = [
            json.dumps({"open": 50000, "close": 50100})
        ]
        result = mgr.get_candles("BTC/USDT", "1h")
        assert len(result) == 1
        assert result[0]["open"] == 50000

    # ── Capital / Metrics ────────────────────────────────────

    def test_update_and_get_capital(self):
        mgr = self._make_db()
        mgr.update_capital(3500.0)
        mgr.client.set.assert_called_with("capital:current", 3500.0)

        mgr.client.get.return_value = "3500.0"
        assert mgr.get_current_capital() == 3500.0

    def test_get_capital_default(self):
        mgr = self._make_db()
        mgr.client.get.return_value = None
        # Should return initial_capital from settings
        capital = mgr.get_current_capital()
        assert capital > 0  # Should be the default (3000.0)

    def test_calculate_metrics_no_trades(self):
        mgr = self._make_db()
        # Make get_trades_history return empty
        with patch.object(mgr, "get_trades_history", return_value=[]):
            metrics = mgr.calculate_metrics()
        assert metrics["total_trades"] == 0
        assert metrics["win_rate"] == 0.0

    def test_calculate_metrics_with_trades(self):
        mgr = self._make_db()
        trades = [
            Trade(
                position_id="p1", pair="BTC/USDT", side="LONG",
                entry_price=50000, exit_price=51000, size=100,
                quantity=0.002, pnl=2.0, pnl_percent=2.0, fees=0.08,
                opened_at=datetime.now(), duration_minutes=30, exit_reason="TP",
            ),
            Trade(
                position_id="p2", pair="BTC/USDT", side="LONG",
                entry_price=50000, exit_price=49000, size=100,
                quantity=0.002, pnl=-2.0, pnl_percent=-2.0, fees=0.08,
                opened_at=datetime.now(), duration_minutes=20, exit_reason="SL",
            ),
        ]
        with patch.object(mgr, "get_trades_history", return_value=trades):
            metrics = mgr.calculate_metrics()

        assert metrics["total_trades"] == 2
        assert metrics["win_rate"] == 50.0
        assert metrics["total_pnl"] == 0.0  # +2 - 2 = 0
