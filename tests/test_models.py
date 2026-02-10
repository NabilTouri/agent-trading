"""
Tests for core.models — Pydantic data models.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError


class TestActionType:
    def test_enum_values(self):
        from core.models import ActionType
        assert ActionType.BUY == "BUY"
        assert ActionType.SELL == "SELL"
        assert ActionType.HOLD == "HOLD"


class TestSignal:
    def test_create_valid(self):
        from core.models import Signal, ActionType

        sig = Signal(
            pair="BTC/USDT",
            action=ActionType.BUY,
            confidence=80.0,
            reasoning="Strong bullish signal",
            agent_votes={"market": "BUY", "risk": "APPROVE"},
            market_data={"price": 50000},
        )
        assert sig.pair == "BTC/USDT"
        assert sig.confidence == 80.0
        assert sig.signal_id.startswith("sig_")
        assert isinstance(sig.timestamp, datetime)

    def test_confidence_bounds(self):
        from core.models import Signal, ActionType

        with pytest.raises(ValidationError):
            Signal(
                pair="BTC/USDT",
                action=ActionType.BUY,
                confidence=150.0,  # > 100
                reasoning="x",
                agent_votes={},
                market_data={},
            )

        with pytest.raises(ValidationError):
            Signal(
                pair="BTC/USDT",
                action=ActionType.BUY,
                confidence=-10.0,  # < 0
                reasoning="x",
                agent_votes={},
                market_data={},
            )

    def test_json_round_trip(self):
        from core.models import Signal, ActionType

        sig = Signal(
            pair="ETH/USDT",
            action=ActionType.SELL,
            confidence=65.0,
            reasoning="Bearish",
            agent_votes={"market": "SELL"},
            market_data={"price": 3000},
        )
        json_str = sig.model_dump_json()
        restored = Signal.model_validate_json(json_str)
        assert restored.pair == sig.pair
        assert restored.action == sig.action


class TestPosition:
    def test_create_valid(self):
        from core.models import Position

        pos = Position(
            pair="BTC/USDT",
            side="LONG",
            entry_price=50000.0,
            size=100.0,
            quantity=0.002,
            stop_loss=49000.0,
            signal_id="sig_123",
        )
        assert pos.side == "LONG"
        assert pos.leverage == 1  # default
        assert pos.take_profit is None  # optional

    def test_invalid_side(self):
        from core.models import Position

        with pytest.raises(ValidationError):
            Position(
                pair="BTC/USDT",
                side="INVALID",
                entry_price=50000.0,
                size=100.0,
                quantity=0.002,
                stop_loss=49000.0,
                signal_id="sig_123",
            )


class TestTrade:
    def test_create_valid(self):
        from core.models import Trade

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
            duration_minutes=45,
            exit_reason="TP",
        )
        assert trade.exit_reason == "TP"
        assert trade.pnl == 2.0

    def test_invalid_exit_reason(self):
        from core.models import Trade

        with pytest.raises(ValidationError):
            Trade(
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
                duration_minutes=45,
                exit_reason="INVALID",
            )


class TestOrderRequest:
    def test_market_order(self):
        from core.models import OrderRequest

        order = OrderRequest(
            pair="BTC/USDT",
            side="BUY",
            order_type="MARKET",
            quantity=0.001,
        )
        assert order.price is None
        assert order.stop_loss is None

    def test_limit_order(self):
        from core.models import OrderRequest

        order = OrderRequest(
            pair="ETH/USDT",
            side="SELL",
            order_type="LIMIT",
            quantity=0.5,
            price=3000.0,
            stop_loss=2900.0,
            take_profit=3200.0,
        )
        assert order.price == 3000.0
