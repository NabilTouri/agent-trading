from fastapi import APIRouter
from datetime import datetime
from core.database import db
from core.exchange import exchange
from core.config import settings
from loguru import logger

router = APIRouter()


@router.get("/metrics")
def get_system_metrics():
    """Get overall system metrics."""
    current_balance = exchange.get_account_balance()
    initial_capital = db.get_initial_capital()

    if initial_capital == 0:
        initial_capital = current_balance
    
    pnl = current_balance - initial_capital
    pnl_percent = (pnl / initial_capital * 100) if initial_capital > 0 else 0.0

    return {
        "capital": {
            "current": current_balance,
            "initial": initial_capital,
            "pnl": round(pnl, 2),
            "pnl_percent": round(pnl_percent, 2)
        },
        "performance": db.calculate_metrics(),
        "positions": {
            "open": len(db.get_all_open_positions()),
            "max": settings.max_positions
        },
        "config": {
            "risk_per_trade": settings.risk_per_trade,
            "max_drawdown": settings.max_drawdown,
            "trading_pairs": settings.pairs_list,
            "testnet": settings.binance_testnet
        }
    }


@router.get("/balance")
def get_exchange_balance():
    """Get balance from Binance."""
    return {
        "usdt_balance": exchange.get_account_balance()
    }

@router.get("/prices")
def get_current_prices():
    """Get current prices for all trading pairs."""
    prices = {}
    for pair in settings.pairs_list:
        prices[pair] = exchange.get_current_price(pair)
    return prices


@router.get("/status")
def get_system_status():
    """Get system component status."""
    status = {}

    # Redis
    try:
        db.client.ping()
        status["redis"] = "connected"
    except Exception as e:
        status["redis"] = f"disconnected"
    
    # Binance — use cached balance instead of making a fresh API call
    # This avoids burning API quota just for a health check
    try:
        balance = exchange._balance_cache.get("balance", 0)
        status["binance"] = "connected" if balance > 0 else "unknown"
    except Exception as e:
        status["binance"] = f"disconnected"

    status["mode"] = "testnet" if settings.binance_testnet else "mainnet"

    return status


@router.get("/health/detailed")
def get_detailed_health():
    """Detailed health check for all system components."""
    health = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "components": {}
    }

    # Check Redis
    try:
        db.client.ping()
        health["components"]["redis"] = {"status": "healthy"}
    except Exception as e:
        health["components"]["redis"] = {"status": "unhealthy", "error": str(e)}
        health["status"] = "degraded"

    # Check Binance API — single call, reuse result
    try:
        balance = exchange.get_account_balance()
        health["components"]["binance"] = {
            "status": "healthy",
            "usdt_balance": balance
        }
    except Exception as e:
        health["components"]["binance"] = {"status": "unhealthy", "error": str(e)}
        health["status"] = "degraded"
        balance = 0.0

    # Check drawdown / risk level — reuse balance from above
    try:
        initial_capital = db.get_initial_capital()

        drawdown = 0.0
        if initial_capital > 0 and balance < initial_capital:
            drawdown = ((initial_capital - balance) / initial_capital) * 100

        risk_status = "healthy"
        if drawdown > settings.max_drawdown * 100:
            risk_status = "critical"
            health["status"] = "critical"
        elif drawdown > settings.max_drawdown * 100 * 0.75:  # 75% of max
            risk_status = "warning"
            if health["status"] == "healthy":
                health["status"] = "degraded"

        health["components"]["risk"] = {
            "status": risk_status,
            "current_drawdown_pct": round(drawdown, 2),
            "max_drawdown_pct": settings.max_drawdown * 100,
            "current_capital": balance,
            "initial_capital": initial_capital
        }
    except Exception as e:
        health["components"]["risk"] = {"status": "unknown", "error": str(e)}

    # Check open positions
    try:
        positions = db.get_all_open_positions()
        health["components"]["positions"] = {
            "status": "healthy" if len(positions) < settings.max_positions else "warning",
            "open": len(positions),
            "max": settings.max_positions
        }
    except Exception as e:
        health["components"]["positions"] = {"status": "unknown", "error": str(e)}

    # Check Anthropic API key is set
    health["components"]["anthropic"] = {
        "status": "healthy" if settings.anthropic_api_key and len(settings.anthropic_api_key) > 10 else "unhealthy"
    }

    return health