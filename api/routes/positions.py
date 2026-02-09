from fastapi import APIRouter
from core.database import db
from core.exchange import exchange

router = APIRouter()


@router.get("/current")
def get_open_positions():
    """Get currently open positions."""
    positions = db.get_all_open_positions()
    
    # Enrich with current prices and unrealized PnL
    result = []
    for pos in positions:
        current_price = exchange.get_current_price(pos.pair)
        
        # Calculate unrealized PnL
        if pos.side == "LONG":
            unrealized_pnl = (current_price - pos.entry_price) * pos.quantity
        else:
            unrealized_pnl = (pos.entry_price - current_price) * pos.quantity
        
        pnl_percent = (unrealized_pnl / pos.size) * 100 if pos.size > 0 else 0
        
        pos_dict = pos.model_dump()
        pos_dict['current_price'] = current_price
        pos_dict['unrealized_pnl'] = round(unrealized_pnl, 2)
        pos_dict['unrealized_pnl_percent'] = round(pnl_percent, 2)
        result.append(pos_dict)
    
    return result


@router.get("/count")
def get_positions_count():
    """Get number of open positions."""
    positions = db.get_all_open_positions()
    return {"count": len(positions)}
