from fastapi import APIRouter
from typing import Optional, List
from core.database import db

router = APIRouter()


@router.get("/")
def get_trades(pair: Optional[str] = None, limit: int = 100):
    """Get trade history."""
    trades = db.get_trades_history(pair=pair, limit=limit)
    return [trade.model_dump() for trade in trades]


@router.get("/stats")
def get_trade_stats():
    """Get trading performance statistics."""
    return db.calculate_metrics()


@router.get("/recent")
def get_recent_trades(limit: int = 10):
    """Get most recent trades."""
    trades = db.get_trades_history(limit=limit)
    return [trade.model_dump() for trade in trades]
