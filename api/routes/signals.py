from fastapi import APIRouter
from typing import Optional
from core.database import db
from core.config import settings

router = APIRouter()


@router.get("/history")
def get_signals_history(pair: Optional[str] = None, limit: int = 50):
    """Get signal history."""
    if pair:
        signals = db.get_signals_history(pair=pair, limit=limit)
        return [signal.model_dump() for signal in signals]
    else:
        # Get from all pairs
        all_signals = []
        for p in settings.pairs_list:
            signals = db.get_signals_history(pair=p, limit=limit)
            all_signals.extend([s.model_dump() for s in signals])
        
        # Sort by timestamp descending
        all_signals.sort(key=lambda x: x['timestamp'], reverse=True)
        return all_signals[:limit]


@router.get("/latest")
def get_latest_signal(pair: str):
    """Get latest signal for pair."""
    signal = db.get_latest_signal(pair)
    if signal:
        return signal.model_dump()
    return {"message": "No signals found", "pair": pair}


@router.get("/latest/all")
def get_latest_signals_all():
    """Get latest signal for all pairs."""
    result = {}
    for pair in settings.pairs_list:
        signal = db.get_latest_signal(pair)
        if signal:
            result[pair] = signal.model_dump()
        else:
            result[pair] = None
    return result
