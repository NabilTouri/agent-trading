"""
Tests for core.exchange — BinanceExchangeWrapper.
All Binance API calls are mocked.
"""

import pytest
from unittest.mock import MagicMock, patch
from binance.exceptions import BinanceAPIException


def _make_api_error(msg="error"):
    """Create a BinanceAPIException with a proper mocked response."""
    resp = MagicMock()
    resp.text = msg
    resp.status_code = 400
    return BinanceAPIException(resp, 400, msg)



class TestBinanceExchangeWrapper:
    """Tests for the exchange wrapper with mocked Binance client."""

    def _make_exchange(self):
        """Create wrapper with mocked client."""
        from core.exchange import BinanceExchangeWrapper

        with patch.object(BinanceExchangeWrapper, "__init__", lambda self: None):
            ex = BinanceExchangeWrapper()
            ex.client = MagicMock()
            ex.testnet = True
            ex.base_url = "https://testnet.binancefuture.com"
            ex._symbol_info_cache = {
                "BTCUSDT": {"quantity_precision": 3, "price_precision": 2, "step_size": 0.001},
                "ETHUSDT": {"quantity_precision": 3, "price_precision": 2, "step_size": 0.001},
            }
        return ex

    # ── Balance ──────────────────────────────────────────────

    def test_get_account_balance_success(self):
        ex = self._make_exchange()
        ex.client.futures_account_balance.return_value = [
            {"asset": "BNB", "balance": "1.0"},
            {"asset": "USDT", "balance": "3000.50"},
        ]
        assert ex.get_account_balance() == 3000.50

    def test_get_account_balance_no_usdt(self):
        ex = self._make_exchange()
        ex.client.futures_account_balance.return_value = [
            {"asset": "BNB", "balance": "1.0"},
        ]
        assert ex.get_account_balance() == 0.0

    def test_get_account_balance_api_error(self):
        ex = self._make_exchange()
        ex.client.futures_account_balance.side_effect = _make_api_error()
        assert ex.get_account_balance() == 0.0

    # ── Price ────────────────────────────────────────────────

    def test_get_current_price(self):
        ex = self._make_exchange()
        ex.client.futures_symbol_ticker.return_value = {"price": "50123.45"}
        assert ex.get_current_price("BTC/USDT") == 50123.45
        ex.client.futures_symbol_ticker.assert_called_with(symbol="BTCUSDT")

    def test_get_current_price_api_error(self):
        ex = self._make_exchange()
        ex.client.futures_symbol_ticker.side_effect = _make_api_error()
        assert ex.get_current_price("BTC/USDT") == 0.0

    # ── Klines ───────────────────────────────────────────────

    def test_get_klines(self):
        ex = self._make_exchange()
        ex.client.futures_klines.return_value = [
            [1700000000, "50000", "50100", "49900", "50050", "1000",
             0, "0", 0, "0", "0", "0"],
        ]
        result = ex.get_klines("ETH/USDT", "1h", 1)
        assert len(result) == 1
        assert result[0]["open"] == 50000.0
        assert result[0]["close"] == 50050.0

    def test_get_klines_api_error(self):
        ex = self._make_exchange()
        ex.client.futures_klines.side_effect = _make_api_error()
        assert ex.get_klines("BTC/USDT", "1h") == []

    # ── Orders ───────────────────────────────────────────────

    def test_place_market_order(self):
        ex = self._make_exchange()
        ex.client.futures_create_order.return_value = {"orderId": 123}
        result = ex.place_market_order("BTC/USDT", "BUY", 0.001)
        assert result == {"orderId": 123}
        ex.client.futures_create_order.assert_called_once()

    def test_place_market_order_fail(self):
        ex = self._make_exchange()
        ex.client.futures_create_order.side_effect = _make_api_error()
        assert ex.place_market_order("BTC/USDT", "BUY", 0.001) is None

    def test_place_limit_order(self):
        ex = self._make_exchange()
        ex.client.futures_create_order.return_value = {"orderId": 456}
        result = ex.place_limit_order("BTC/USDT", "SELL", 0.001, 55000.0)
        assert result is not None

    # ── Leverage ─────────────────────────────────────────────

    def test_set_leverage(self):
        ex = self._make_exchange()
        assert ex.set_leverage("BTC/USDT", 5) is True
        ex.client.futures_change_leverage.assert_called_with(
            symbol="BTCUSDT", leverage=5
        )

    def test_set_leverage_fail(self):
        ex = self._make_exchange()
        ex.client.futures_change_leverage.side_effect = _make_api_error()
        assert ex.set_leverage("BTC/USDT", 5) is False

    # ── Positions ────────────────────────────────────────────

    def test_get_position_info_long(self):
        ex = self._make_exchange()
        ex.client.futures_position_information.return_value = [
            {
                "symbol": "BTCUSDT",
                "positionAmt": "0.001",
                "entryPrice": "50000",
                "unRealizedProfit": "5.0",
                "leverage": "3",
            }
        ]
        info = ex.get_position_info("BTC/USDT")
        assert info["side"] == "LONG"
        assert info["quantity"] == 0.001

    def test_get_position_info_short(self):
        ex = self._make_exchange()
        ex.client.futures_position_information.return_value = [
            {
                "symbol": "BTCUSDT",
                "positionAmt": "-0.002",
                "entryPrice": "50000",
                "unRealizedProfit": "-3.0",
                "leverage": "2",
            }
        ]
        info = ex.get_position_info("BTC/USDT")
        assert info["side"] == "SHORT"

    def test_get_position_info_none(self):
        ex = self._make_exchange()
        ex.client.futures_position_information.return_value = [
            {"symbol": "BTCUSDT", "positionAmt": "0", "entryPrice": "0",
             "unRealizedProfit": "0", "leverage": "1"}
        ]
        assert ex.get_position_info("BTC/USDT") is None

    # ── Close position ───────────────────────────────────────

    def test_close_position_success(self):
        ex = self._make_exchange()
        ex.client.futures_position_information.return_value = [
            {
                "symbol": "BTCUSDT",
                "positionAmt": "0.001",
                "entryPrice": "50000",
                "unRealizedProfit": "5.0",
                "leverage": "3",
            }
        ]
        ex.client.futures_create_order.return_value = {"orderId": 789}
        assert ex.close_position("BTC/USDT") is True

    def test_close_position_no_position(self):
        ex = self._make_exchange()
        ex.client.futures_position_information.return_value = [
            {"symbol": "BTCUSDT", "positionAmt": "0", "entryPrice": "0",
             "unRealizedProfit": "0", "leverage": "1"}
        ]
        assert ex.close_position("BTC/USDT") is False

    # ── Open orders & cancel ─────────────────────────────────

    def test_get_open_orders(self):
        ex = self._make_exchange()
        ex.client.futures_get_open_orders.return_value = [{"orderId": 1}]
        assert len(ex.get_open_orders("BTC/USDT")) == 1

    def test_cancel_all_orders(self):
        ex = self._make_exchange()
        assert ex.cancel_all_orders("BTC/USDT") is True
        ex.client.futures_cancel_all_open_orders.assert_called_with(symbol="BTCUSDT")
