"""
Tests for core.config — Settings model.
"""

import pytest
from unittest.mock import patch
import os


class TestSettings:
    """Test the Pydantic Settings model."""

    def test_default_values(self):
        """Settings should load with sane defaults when no env vars are set."""
        from core.config import Settings

        with patch.dict(os.environ, {}, clear=True):
            s = Settings(_env_file=None)

        assert s.binance_testnet is True
        assert s.redis_host == "redis"
        assert s.redis_port == 6379
        assert s.risk_per_trade == 0.02
        assert s.max_positions == 3
        assert s.log_level == "INFO"
        assert s.api_host == "0.0.0.0"
        assert s.api_port == 8000

    def test_env_override(self):
        """Environment variables should override defaults."""
        from core.config import Settings

        env = {
            "BINANCE_TESTNET": "false",
            "MAX_POSITIONS": "5",
            "TRADING_PAIRS": "SOL/USDT,DOGE/USDT",
        }
        with patch.dict(os.environ, env, clear=True):
            s = Settings(_env_file=None)

        assert s.binance_testnet is False
        assert s.max_positions == 5
        assert s.trading_pairs == "SOL/USDT,DOGE/USDT"

    def test_pairs_list_property(self):
        """pairs_list should split and strip comma-separated pairs."""
        from core.config import Settings

        env = {"TRADING_PAIRS": "BTC/USDT, ETH/USDT , SOL/USDT"}
        with patch.dict(os.environ, env, clear=True):
            s = Settings(_env_file=None)

        assert s.pairs_list == ["BTC/USDT", "ETH/USDT", "SOL/USDT"]

    def test_extra_env_vars_ignored(self):
        """Extra env vars (e.g. NEXT_PUBLIC_API_URL) should be silently ignored."""
        from core.config import Settings

        env = {"NEXT_PUBLIC_API_URL": "http://localhost:8000", "SOME_RANDOM": "value"}
        with patch.dict(os.environ, env, clear=True):
            s = Settings(_env_file=None)

        # Should not raise
        assert s.redis_host == "redis"

    def test_crewai_defaults(self):
        """CrewAI-related settings should have sane defaults."""
        from core.config import Settings

        with patch.dict(os.environ, {}, clear=True):
            s = Settings(_env_file=None)

        assert s.crew_model == "claude-sonnet-4-20250514"
        assert 0 <= s.crew_temperature <= 1.0
        assert s.daily_cost_limit_usd > 0
        assert s.monthly_cost_limit_usd > 0

    def test_safeguard_defaults(self):
        """Safeguard thresholds should have sane defaults."""
        from core.config import Settings

        with patch.dict(os.environ, {}, clear=True):
            s = Settings(_env_file=None)

        assert s.min_confidence > 0
        assert s.min_rr_ratio > 0
        assert s.max_sl_distance_pct > 0
        assert s.max_trades_per_day > 0
