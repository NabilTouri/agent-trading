"""
Tests for core.data_pipeline — DataPipeline.
Exchange and DB are mocked.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock


class TestDataPipeline:
    """Tests for DataPipeline with mocked exchange and DB."""

    def _make_pipeline(self):
        from core.data_pipeline import DataPipeline
        return DataPipeline()

    # ── Technical Indicators ─────────────────────────────────

    def test_calculate_indicators_enough_data(self, sample_candles):
        pipeline = self._make_pipeline()
        indicators = pipeline._calculate_indicators(sample_candles)

        assert "rsi" in indicators
        assert "macd" in indicators
        assert "macd_signal" in indicators
        assert "bb_upper" in indicators
        assert "bb_lower" in indicators
        assert "atr" in indicators
        # RSI should be a reasonable value
        assert 0 <= indicators["rsi"] <= 100

    def test_calculate_indicators_insufficient_data(self):
        pipeline = self._make_pipeline()
        candles = [{"open": 100, "high": 110, "low": 90, "close": 105, "volume": 10}] * 5
        indicators = pipeline._calculate_indicators(candles)
        assert indicators["rsi"] == 50.0  # fallback

    # ── Price changes ────────────────────────────────────────

    def test_calculate_changes(self, sample_candles):
        pipeline = self._make_pipeline()
        changes = pipeline._calculate_changes(sample_candles)
        assert "1h" in changes
        assert "4h" in changes
        assert "24h" in changes
        assert isinstance(changes["1h"], float)

    def test_calculate_changes_insufficient_data(self):
        pipeline = self._make_pipeline()
        candles = [{"close": 100}] * 5
        changes = pipeline._calculate_changes(candles)
        assert changes == {"1h": 0.0, "4h": 0.0, "24h": 0.0}

    # ── Volume ───────────────────────────────────────────────

    def test_calculate_volume_24h(self, sample_candles):
        pipeline = self._make_pipeline()
        vol = pipeline._calculate_volume_24h(sample_candles)
        assert vol > 0

    def test_calculate_volume_24h_insufficient(self):
        pipeline = self._make_pipeline()
        candles = [{"volume": 100}] * 5
        assert pipeline._calculate_volume_24h(candles) == 0.0

    # ── Volatility ───────────────────────────────────────────

    def test_calculate_volatility_low(self):
        pipeline = self._make_pipeline()
        # Very stable prices → LOW volatility
        candles = [{"close": 100.0 + i * 0.01} for i in range(25)]
        vol = pipeline._calculate_volatility(candles)
        assert vol == "LOW"

    def test_calculate_volatility_high(self):
        pipeline = self._make_pipeline()
        # Wild swings → HIGH volatility
        candles = [{"close": 100 + (i % 2) * 50} for i in range(25)]
        vol = pipeline._calculate_volatility(candles)
        assert vol == "HIGH"

    def test_calculate_volatility_insufficient(self):
        pipeline = self._make_pipeline()
        candles = [{"close": 100}] * 5
        assert pipeline._calculate_volatility(candles) == "UNKNOWN"

    # ── Fetch and cache ──────────────────────────────────────

    def test_fetch_and_cache_uses_cache(self, sample_candles):
        pipeline = self._make_pipeline()
        with patch("core.data_pipeline.db") as mock_db, \
             patch("core.data_pipeline.exchange") as mock_ex:
            mock_db.get_candles.return_value = sample_candles
            result = pipeline._fetch_and_cache_candles("BTC/USDT", "1h", 30)
            assert len(result) == 30
            mock_ex.get_klines.assert_not_called()

    def test_fetch_and_cache_fetches_fresh(self, sample_candles):
        pipeline = self._make_pipeline()
        with patch("core.data_pipeline.db") as mock_db, \
             patch("core.data_pipeline.exchange") as mock_ex:
            mock_db.get_candles.return_value = []  # cache miss
            mock_ex.get_klines.return_value = sample_candles
            result = pipeline._fetch_and_cache_candles("BTC/USDT", "1h", 30)
            assert len(result) == 30
            mock_ex.get_klines.assert_called_once()
            mock_db.save_candles.assert_called_once()

    # ── Full fetch_market_data ───────────────────────────────

    @pytest.mark.asyncio
    async def test_fetch_market_data(self, sample_candles):
        pipeline = self._make_pipeline()
        with patch("core.data_pipeline.db") as mock_db, \
             patch("core.data_pipeline.exchange") as mock_ex:
            mock_db.get_candles.return_value = sample_candles
            mock_ex.get_current_price.return_value = 50500.0

            data = await pipeline.fetch_market_data("BTC/USDT")

            assert data["pair"] == "BTC/USDT"
            assert data["current_price"] == 50500.0
            assert "indicators" in data
            assert "change_1h" in data
            assert "volatility" in data
