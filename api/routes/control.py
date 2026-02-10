from fastapi import APIRouter, HTTPException
from core.database import db
from core.exchange import exchange
from core.config import settings
from loguru import logger

router = APIRouter()


@router.post("/emergency-stop")
def emergency_stop():
    """Emergency stop: close all positions."""
    try:
        positions = db.get_all_open_positions()
        closed = 0
        errors = []
        
        for pos in positions:
            try:
                success = exchange.close_position(pos.pair)
                if success:
                    db.close_position(pos.position_id)
                    closed += 1
                    logger.warning(f"Emergency closed position: {pos.pair}")
                else:
                    errors.append(pos.pair)
            except Exception as e:
                errors.append(f"{pos.pair}: {str(e)}")
        
        return {
            "message": "Emergency stop executed",
            "positions_closed": closed,
            "errors": errors
        }
    except Exception as e:
        logger.error(f"Emergency stop failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pause")
def pause_trading():
    """Pause trading (placeholder)."""
    # TODO: Implement pause mechanism
    return {"message": "Trading paused", "status": "not_implemented"}


@router.post("/resume")
def resume_trading():
    """Resume trading (placeholder)."""
    # TODO: Implement resume mechanism
    return {"message": "Trading resumed", "status": "not_implemented"}


@router.post("/reset-capital")
def reset_capital():
    """Reset initial capital to current broker balance."""
    broker_balance = exchange.get_account_balance()
    db.reset_initial_capital(broker_balance)
    logger.info(f"Capital reset to broker balance: ${broker_balance:.2f}")
    return {
        "message": "Capital reset to current broker balance",
        "new_capital": broker_balance
    }
