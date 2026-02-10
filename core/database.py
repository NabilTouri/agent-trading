import redis
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from loguru import logger
from core.config import settings
from core.models import Signal, Position, Trade


class RedisManager:
    """Redis database manager for trading data."""
    
    def __init__(self):
        self.client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            password=settings.redis_password.strip() or None,
            decode_responses=True
        )
        try:
            self.client.ping()
            logger.info("Redis connected successfully")
        except redis.ConnectionError as e:
            logger.error(f"Redis connection failed: {e}")
            raise
    
    # === SIGNALS ===
    def save_signal(self, signal: Signal) -> None:
        """Save signal to Redis (keep last 100)."""
        key = f"signals:{signal.pair}"
        self.client.lpush(key, signal.model_dump_json())
        self.client.ltrim(key, 0, 99)  # Keep last 100
        self.client.expire(key, 60 * 60 * 24 * 30)  # 30 days
    
    def get_latest_signal(self, pair: str) -> Optional[Signal]:
        """Get latest signal for pair."""
        key = f"signals:{pair}"
        data = self.client.lindex(key, 0)
        return Signal.model_validate_json(data) if data else None
    
    def get_signals_history(self, pair: str, limit: int = 50) -> List[Signal]:
        """Get signal history for pair."""
        key = f"signals:{pair}"
        data = self.client.lrange(key, 0, limit - 1)
        return [Signal.model_validate_json(d) for d in data]
    
    # === POSITIONS ===
    def save_position(self, position: Position) -> None:
        """Save open position."""
        key = f"positions:open:{position.position_id}"
        self.client.setex(key, 60 * 60 * 24 * 7, position.model_dump_json())
        
        # Add to active positions set
        self.client.sadd("positions:active", position.position_id)
    
    def get_position(self, position_id: str) -> Optional[Position]:
        """Get position by ID."""
        key = f"positions:open:{position_id}"
        data = self.client.get(key)
        return Position.model_validate_json(data) if data else None
    
    def get_all_open_positions(self) -> List[Position]:
        """Get all open positions."""
        position_ids = self.client.smembers("positions:active")
        positions = []
        for pid in position_ids:
            pos = self.get_position(pid)
            if pos:
                positions.append(pos)
        return positions
    
    def close_position(self, position_id: str) -> None:
        """Close position (remove from active)."""
        self.client.srem("positions:active", position_id)
        key = f"positions:open:{position_id}"
        self.client.delete(key)
    
    # === TRADES ===
    def save_trade(self, trade: Trade) -> None:
        """Save completed trade."""
        key = f"trades:history:{trade.pair}"
        self.client.lpush(key, trade.model_dump_json())
        self.client.ltrim(key, 0, 499)  # Keep last 500
    
    def get_trades_history(self, pair: Optional[str] = None, limit: int = 100) -> List[Trade]:
        """Get trade history."""
        if pair:
            key = f"trades:history:{pair}"
            data = self.client.lrange(key, 0, limit - 1)
        else:
            # Get from all pairs
            data = []
            for p in settings.pairs_list:
                key = f"trades:history:{p}"
                data.extend(self.client.lrange(key, 0, limit - 1))
        
        trades = [Trade.model_validate_json(d) for d in data[:limit]]
        return sorted(trades, key=lambda t: t.closed_at, reverse=True)
    
    # === OHLCV DATA ===
    def save_candles(self, pair: str, timeframe: str, candles: List[Dict]) -> None:
        """Save OHLCV candles (keep 7 days)."""
        key = f"candles:{pair}:{timeframe}"
        
        # Clear existing and add new
        pipeline = self.client.pipeline()
        pipeline.delete(key)
        for candle in candles:
            pipeline.rpush(key, json.dumps(candle))
        
        # Set max candles based on timeframe
        max_candles = {
            "1m": 7 * 24 * 60,
            "5m": 7 * 24 * 12,
            "15m": 7 * 24 * 4,
            "1h": 7 * 24,
            "4h": 7 * 6
        }.get(timeframe, 500)
        
        pipeline.ltrim(key, 0, max_candles - 1)
        pipeline.expire(key, 60 * 60 * 24 * 7)
        pipeline.execute()
    
    def get_candles(self, pair: str, timeframe: str, limit: int = 500) -> List[Dict]:
        """Get OHLCV candles."""
        key = f"candles:{pair}:{timeframe}"
        data = self.client.lrange(key, 0, limit - 1)
        return [json.loads(d) for d in data]
    
    # === METRICS ===
    def update_capital(self, new_capital: float) -> None:
        """Update current capital."""
        self.client.set("capital:current", new_capital)
        
        # Daily capital snapshot
        date_key = datetime.now().strftime("%Y-%m-%d")
        self.client.hset("capital:daily", date_key, new_capital)
    
    def get_current_capital(self) -> float:
        """Get current capital."""
        capital = self.client.get("capital:current")
        return float(capital) if capital else settings.initial_capital
    
    def calculate_metrics(self) -> Dict[str, Any]:
        """Calculate performance metrics."""
        trades = self.get_trades_history(limit=1000)
        if not trades:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "avg_profit": 0.0,
                "avg_loss": 0.0,
                "profit_factor": 0.0,
                "total_pnl": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0
            }
        
        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl < 0]
        
        win_rate = len(wins) / len(trades) * 100 if trades else 0
        avg_profit = sum(t.pnl for t in wins) / len(wins) if wins else 0
        avg_loss = abs(sum(t.pnl for t in losses) / len(losses)) if losses else 0
        profit_factor = avg_profit / avg_loss if avg_loss > 0 else 0
        total_pnl = sum(t.pnl for t in trades)
        
        return {
            "total_trades": len(trades),
            "win_rate": round(win_rate, 2),
            "avg_profit": round(avg_profit, 2),
            "avg_loss": round(avg_loss, 2),
            "profit_factor": round(profit_factor, 2),
            "total_pnl": round(total_pnl, 2),
            "sharpe_ratio": 0.0,  # TODO: implement proper Sharpe calculation
            "max_drawdown": 0.0  # TODO: implement drawdown tracking
        }


# Singleton instance
db = RedisManager()
