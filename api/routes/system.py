from fastapi import APIRouter
from core.database import db
from core.exchange import exchange
from core.config import settings

router = APIRouter()


@router.get("/metrics")
def get_system_metrics():
    """Get overall system metrics."""
    current = exchange.get_account_balance()
    initial = db.get_initial_capital()
    pnl = current - initial if initial > 0 else 0
    pnl_percent = (pnl / initial) * 100 if initial > 0 else 0
    
    return {
        "capital": {
            "current": current,
            "initial": initial,
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
    result = {}
    for pair in settings.pairs_list:
        result[pair] = exchange.get_current_price(pair)
    return result


@router.get("/status")
def get_system_status():
    """Get system status."""
    try:
        # Check Redis
        db.client.ping()
        redis_status = "connected"
    except Exception:
        redis_status = "disconnected"
    
    try:
        # Check Binance
        exchange.get_account_balance()
        binance_status = "connected"
    except Exception:
        binance_status = "disconnected"
    
    return {
        "redis": redis_status,
        "binance": binance_status,
        "mode": "testnet" if settings.binance_testnet else "mainnet"
    }
