"""
Shared fixtures for all tests.
Mocks external services (Redis, Binance, Telegram) so tests run
without any running infrastructure.

NOTE: anthropic SDK is no longer used directly — CrewAI uses LiteLLM.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime


# ── Patch singletons BEFORE they are imported by other modules ──────────────

@pytest.fixture(autouse=True)
def _patch_singletons(monkeypatch):
    """Prevent singleton modules from connecting to real services on import."""
    # Patch Redis connection at module level
    monkeypatch.setattr("redis.Redis", lambda **kw: _make_fake_redis())
    # Patch Binance client
    monkeypatch.setattr("binance.client.Client.__init__", lambda *a, **kw: None)


def _make_fake_redis():
    """Return a MagicMock that behaves like a redis.Redis client."""
    r = MagicMock()
    r.ping.return_value = True
    r.get.return_value = None
    r.set.return_value = True
    r.lpush.return_value = 1
    r.rpush.return_value = 1
    r.ltrim.return_value = True
    r.lrange.return_value = []
    r.lindex.return_value = None
    r.smembers.return_value = set()
    r.sadd.return_value = 1
    r.srem.return_value = 1
    r.delete.return_value = 1
    r.setex.return_value = True
    r.expire.return_value = True
    r.hset.return_value = 1
    r.pipeline.return_value = MagicMock()
    return r


# ── Reusable data factories ─────────────────────────────────────────────────

@pytest.fixture
def sample_candles():
    """Generate 30 realistic 1h candles."""
    base = 50000.0
    candles = []
    for i in range(30):
        o = base + i * 10
        candles.append({
            "timestamp": 1700000000 + i * 3600,
            "open": o,
            "high": o + 50,
            "low": o - 40,
            "close": o + 20,
            "volume": 1000 + i * 5,
        })
    return candles


@pytest.fixture
def sample_market_data(sample_candles):
    """Full market_data dict expected by legacy agents / data pipeline."""
    return {
        "pair": "BTC/USDT",
        "current_price": 50500.0,
        "candles_15m": sample_candles[:10],
        "candles_1h": sample_candles,
        "candles_4h": sample_candles[:10],
        "indicators": {
            "rsi": 55.0,
            "macd": 100.0,
            "macd_signal": 80.0,
            "bb_upper": 51000.0,
            "bb_lower": 49000.0,
            "atr": 500.0,
        },
        "volume_24h": 1_000_000,
        "change_1h": 0.5,
        "change_4h": 1.2,
        "change_24h": 2.5,
        "volatility": "MEDIUM",
        "atr": 500.0,
        "risk_per_trade": 0.02,
        "entry_price": 50500.0,
    }


@pytest.fixture
def sample_trade_decision():
    """Create a sample TradeDecision for tests."""
    from core.models import TradeDecision, EntryPlan, StopLossLevel, TakeProfitLevel

    return TradeDecision(
        decision="APPROVED",
        pair="BTC/USDT",
        direction="LONG",
        confidence=75,
        position_size_usd=200.0,
        position_size_pct=2.0,
        entry=EntryPlan(method="LIMIT", price=50000.0),
        stop_loss=StopLossLevel(price=48500.0, pct=3.0, type="STOP_LIMIT"),
        take_profit=[
            TakeProfitLevel(level=1, price=52000.0, size_pct=50),
            TakeProfitLevel(level=2, price=54000.0, size_pct=50),
        ],
        risk_reward_ratio=2.67,
        reasoning="Strong uptrend confirmed by multiple agents",
    )
