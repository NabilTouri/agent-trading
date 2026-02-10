"""
Tests for API routes (FastAPI TestClient).
Uses mocked database and exchange singletons.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from core.models import Signal, Position, Trade, ActionType


# We need to mock the singletons BEFORE importing the FastAPI app
@pytest.fixture
def client():
    """Create a TestClient with mocked DB and exchange."""
    with patch("core.database.RedisManager") as MockDB, \
         patch("core.exchange.BinanceExchangeWrapper") as MockExchange:

        # Configure mock DB
        mock_db = MagicMock()
        mock_db.get_initial_capital.return_value = 3000.0
        mock_db.get_all_open_positions.return_value = []
        mock_db.calculate_metrics.return_value = {
            "total_trades": 10,
            "win_rate": 60.0,
            "avg_profit": 5.0,
            "avg_loss": 3.0,
            "profit_factor": 1.67,
            "total_pnl": 20.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
        }
        mock_db.get_trades_history.return_value = []
        mock_db.get_signals_history.return_value = []
        mock_db.get_latest_signal.return_value = None
        mock_db.client.ping.return_value = True

        # Configure mock exchange
        mock_exchange = MagicMock()
        mock_exchange.get_account_balance.return_value = 3000.0
        mock_exchange.get_current_price.return_value = 50000.0

        # Patch the module-level singletons
        with patch("api.routes.system.db", mock_db), \
             patch("api.routes.system.exchange", mock_exchange), \
             patch("api.routes.system.settings") as mock_settings, \
             patch("api.routes.trades.db", mock_db), \
             patch("api.routes.positions.db", mock_db), \
             patch("api.routes.positions.exchange", mock_exchange), \
             patch("api.routes.signals.db", mock_db), \
             patch("api.routes.signals.settings") as mock_signals_settings, \
             patch("api.routes.control.db", mock_db), \
             patch("api.routes.control.exchange", mock_exchange), \
             patch("api.routes.control.settings") as mock_ctrl_settings:

            mock_settings.risk_per_trade = 0.02
            mock_settings.max_drawdown = 0.20
            mock_settings.pairs_list = ["BTC/USDT", "ETH/USDT"]
            mock_settings.binance_testnet = True
            mock_settings.max_positions = 3
            mock_signals_settings.pairs_list = ["BTC/USDT", "ETH/USDT"]

            from fastapi.testclient import TestClient
            from api.main import app

            yield TestClient(app)


class TestRootEndpoints:
    def test_root(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert r.json()["status"] == "running"

    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"


class TestSystemRoutes:
    def test_get_metrics(self, client):
        r = client.get("/api/system/metrics")
        assert r.status_code == 200
        data = r.json()
        assert "capital" in data
        assert "performance" in data
        assert "config" in data
        assert data["capital"]["current"] == 3000.0

    def test_get_balance(self, client):
        r = client.get("/api/system/balance")
        assert r.status_code == 200
        assert r.json()["usdt_balance"] == 3000.0

    def test_get_prices(self, client):
        r = client.get("/api/system/prices")
        assert r.status_code == 200
        data = r.json()
        assert "BTC/USDT" in data

    def test_get_status(self, client):
        r = client.get("/api/system/status")
        assert r.status_code == 200
        data = r.json()
        assert data["redis"] == "connected"
        assert data["mode"] == "testnet"


class TestTradeRoutes:
    def test_get_trades_empty(self, client):
        r = client.get("/api/trades/")
        assert r.status_code == 200
        assert r.json() == []

    def test_get_trade_stats(self, client):
        r = client.get("/api/trades/stats")
        assert r.status_code == 200
        data = r.json()
        assert data["total_trades"] == 10
        assert data["win_rate"] == 60.0

    def test_get_recent_trades(self, client):
        r = client.get("/api/trades/recent?limit=5")
        assert r.status_code == 200


class TestPositionRoutes:
    def test_get_open_positions_empty(self, client):
        r = client.get("/api/positions/current")
        assert r.status_code == 200
        assert r.json() == []

    def test_get_positions_count(self, client):
        r = client.get("/api/positions/count")
        assert r.status_code == 200
        assert r.json()["count"] == 0


class TestSignalRoutes:
    def test_get_signals_history(self, client):
        r = client.get("/api/signals/history")
        assert r.status_code == 200

    def test_get_latest_signal_not_found(self, client):
        r = client.get("/api/signals/latest?pair=BTC/USDT")
        assert r.status_code == 200
        assert "message" in r.json()

    def test_get_latest_all(self, client):
        r = client.get("/api/signals/latest/all")
        assert r.status_code == 200


class TestControlRoutes:
    def test_emergency_stop_no_positions(self, client):
        r = client.post("/api/control/emergency-stop")
        assert r.status_code == 200
        data = r.json()
        assert data["positions_closed"] == 0

    def test_pause(self, client):
        r = client.post("/api/control/pause")
        assert r.status_code == 200

    def test_resume(self, client):
        r = client.post("/api/control/resume")
        assert r.status_code == 200

    def test_reset_capital(self, client):
        r = client.post("/api/control/reset-capital")
        assert r.status_code == 200
        assert r.json()["new_capital"] == 3000.0
