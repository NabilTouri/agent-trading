"""
Tests for Pydantic models.

Tests serialization, validation, and defaults for all new CrewAI models.
"""

import pytest
from core.models import (
    TradeDecision, EntryPlan, EntryOrder, StopLossLevel, TakeProfitLevel,
    Signal, Position, Trade, ActionType,
    SafeguardResult, SafeguardReport,
)


class TestTradeDecision:
    def test_valid_approved_decision(self):
        decision = TradeDecision(
            decision="APPROVED",
            pair="BTC/USDT",
            direction="LONG",
            confidence=80,
            position_size_usd=500.0,
            position_size_pct=2.5,
            entry=EntryPlan(method="LIMIT", price=50000.0, orders=[
                EntryOrder(price=49900.0, size=250.0),
                EntryOrder(price=50000.0, size=250.0),
            ]),
            stop_loss=StopLossLevel(price=48500.0, pct=3.0, type="STOP_LIMIT"),
            take_profit=[
                TakeProfitLevel(level=1, price=52000.0, size_pct=50),
                TakeProfitLevel(level=2, price=54000.0, size_pct=50),
            ],
            risk_reward_ratio=2.67,
            reasoning="Strong technical setup",
        )
        assert decision.decision == "APPROVED"
        assert decision.confidence == 80
        assert len(decision.take_profit) == 2

    def test_rejected_decision(self):
        decision = TradeDecision(
            decision="REJECTED",
            pair="ETH/USDT",
            direction="SHORT",
            confidence=40,
            position_size_usd=0,
            position_size_pct=0,
            entry=EntryPlan(method="MARKET", price=3000.0),
            stop_loss=StopLossLevel(price=3100.0, pct=3.3, type="STOP_MARKET"),
            risk_reward_ratio=1.2,
            reasoning="Insufficient confidence",
        )
        assert decision.decision == "REJECTED"

    def test_confidence_bounds(self):
        with pytest.raises(Exception):
            TradeDecision(
                decision="APPROVED",
                pair="BTC/USDT",
                direction="LONG",
                confidence=150,  # Invalid: >100
                position_size_usd=100,
                position_size_pct=1,
                entry=EntryPlan(method="MARKET", price=50000),
                stop_loss=StopLossLevel(price=49000, pct=2, type="STOP_LIMIT"),
                risk_reward_ratio=2.0,
                reasoning="test",
            )

    def test_json_serialization(self):
        decision = TradeDecision(
            decision="APPROVED",
            pair="BTC/USDT",
            direction="LONG",
            confidence=70,
            position_size_usd=200,
            position_size_pct=1,
            entry=EntryPlan(method="MARKET", price=50000),
            stop_loss=StopLossLevel(price=49000, pct=2, type="STOP_LIMIT"),
            risk_reward_ratio=2.5,
            reasoning="test",
        )
        data = decision.model_dump()
        assert data["decision"] == "APPROVED"
        assert data["entry"]["method"] == "MARKET"


class TestSafeguardReport:
    def test_approved_report(self):
        report = SafeguardReport(
            approved=True,
            checks=[
                SafeguardResult(check_name="confidence", passed=True, reason="OK"),
                SafeguardResult(check_name="rr_ratio", passed=True, reason="OK"),
            ],
        )
        assert report.approved is True
        assert len(report.checks) == 2

    def test_rejected_report(self):
        report = SafeguardReport(
            approved=False,
            checks=[
                SafeguardResult(check_name="confidence", passed=False, reason="Too low"),
            ],
            blocked_reason="Confidence too low",
        )
        assert report.approved is False
        assert report.blocked_reason == "Confidence too low"


class TestLegacyModels:
    def test_signal_creation(self):
        signal = Signal(
            pair="BTC/USDT",
            action=ActionType.BUY,
            confidence=85.0,
            reasoning="Test",
            agent_votes={"market": "BUY"},
            market_data={"price": 50000},
        )
        assert signal.action == ActionType.BUY
        assert signal.signal_id.startswith("sig_")

    def test_position_creation(self):
        pos = Position(
            pair="BTC/USDT",
            side="LONG",
            entry_price=50000.0,
            size=500.0,
            quantity=0.01,
            stop_loss=49000.0,
            signal_id="sig_123",
        )
        assert pos.side == "LONG"
        assert pos.position_id  # UUID should be generated
