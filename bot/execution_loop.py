import asyncio
from loguru import logger
from datetime import datetime
import uuid
from core.config import settings
from core.database import db
from core.exchange import exchange
from core.models import Signal, Position, Trade, ActionType
from services.telegram_bot import telegram_notifier


class ExecutionLoop:
    """Execution loop: every 10sec checks signals and executes trades."""
    
    def __init__(self):
        self.interval = settings.execution_interval_seconds
        logger.info(f"ExecutionLoop initialized (interval: {self.interval}s)")
    
    async def run(self):
        """Main loop."""
        # Initial delay
        await asyncio.sleep(10)
        
        while True:
            try:
                # 1. Check active signals
                await self.check_signals()
                
                # 2. Monitor open positions (stop loss / take profit)
                await self.monitor_positions()
                
            except Exception as e:
                logger.error(f"Execution loop error: {e}")
            
            await asyncio.sleep(self.interval)
    
    async def check_signals(self):
        """Check recent signals and execute if valid."""
        for pair in settings.pairs_list:
            signal = db.get_latest_signal(pair)
            
            if not signal:
                continue
            
            # Check if signal is recent (<5 min)
            signal_age = (datetime.now() - signal.timestamp).total_seconds()
            if signal_age > 300:  # 5 minutes
                continue
            
            # Check if confidence is sufficient
            if signal.confidence < 60:
                continue
            
            # Check if action is BUY/SELL (not HOLD)
            if signal.action == ActionType.HOLD:
                continue
            
            # Check if position already open for this pair
            open_positions = db.get_all_open_positions()
            if any(p.pair == pair for p in open_positions):
                logger.debug(f"Position already open for {pair}, skipping")
                continue
            
            # Check max positions
            if len(open_positions) >= settings.max_positions:
                logger.warning(f"Max positions ({settings.max_positions}) reached")
                continue
            
            # EXECUTE TRADE
            await self.execute_signal(signal)
    
    async def execute_signal(self, signal: Signal):
        """Execute signal by opening position."""
        try:
            logger.info(f"EXECUTING signal: {signal.action} {signal.pair}")
            
            # Get data from signal
            position_size = signal.market_data.get('position_size', 0)
            stop_loss = signal.market_data.get('stop_loss', 0)
            take_profit = signal.market_data.get('take_profit', 0)
            current_price = exchange.get_current_price(signal.pair)
            
            if position_size == 0:
                logger.error("Position size is 0, aborting")
                return
            
            if current_price == 0:
                logger.error("Could not get current price, aborting")
                return
            
            # Calculate quantity to buy
            quantity = position_size / current_price
            
            # Determine side
            side = "BUY" if signal.action == ActionType.BUY else "SELL"
            position_side = "LONG" if signal.action == ActionType.BUY else "SHORT"
            
            # Place market order
            order = exchange.place_market_order(signal.pair, side, quantity)
            
            if not order:
                logger.error("Order failed")
                return
            
            # Create Position object
            position = Position(
                position_id=str(uuid.uuid4()),
                pair=signal.pair,
                side=position_side,
                entry_price=current_price,
                size=position_size,
                quantity=quantity,
                stop_loss=stop_loss,
                take_profit=take_profit,
                opened_at=datetime.now(),
                signal_id=signal.signal_id
            )
            
            # Save to DB
            db.save_position(position)
            
            logger.success(
                f"✅ Position opened: {position_side} {quantity:.6f} "
                f"{signal.pair} @ ${current_price:.2f}"
            )
            
            # Telegram notification
            await telegram_notifier.send_message(f"""
✅ <b>POSITION OPENED</b>

{position_side} {signal.pair}
Entry: ${current_price:.2f}
Size: ${position_size:.2f}
Quantity: {quantity:.6f}
Stop Loss: ${stop_loss:.2f}
Take Profit: ${take_profit:.2f}

Confidence: {signal.confidence}%
""")
        
        except Exception as e:
            logger.error(f"Error executing signal: {e}")
            import traceback
            traceback.print_exc()
    
    async def monitor_positions(self):
        """Monitor open positions for stop loss / take profit."""
        positions = db.get_all_open_positions()
        
        for position in positions:
            try:
                current_price = exchange.get_current_price(position.pair)
                
                if current_price == 0:
                    continue
                
                should_close = False
                exit_reason = None
                
                # Check Stop Loss
                if position.side == "LONG" and current_price <= position.stop_loss:
                    should_close = True
                    exit_reason = "SL"
                    logger.warning(f"Stop Loss hit for {position.pair}")
                
                elif position.side == "SHORT" and current_price >= position.stop_loss:
                    should_close = True
                    exit_reason = "SL"
                    logger.warning(f"Stop Loss hit for {position.pair}")
                
                # Check Take Profit
                if position.take_profit and position.take_profit > 0:
                    if position.side == "LONG" and current_price >= position.take_profit:
                        should_close = True
                        exit_reason = "TP"
                        logger.info(f"Take Profit hit for {position.pair}")
                    
                    elif position.side == "SHORT" and current_price <= position.take_profit:
                        should_close = True
                        exit_reason = "TP"
                        logger.info(f"Take Profit hit for {position.pair}")
                
                # Check opposite signal
                latest_signal = db.get_latest_signal(position.pair)
                if latest_signal:
                    signal_age = (datetime.now() - latest_signal.timestamp).total_seconds()
                    
                    if signal_age < 300 and latest_signal.confidence >= 60:
                        if (position.side == "LONG" and latest_signal.action == ActionType.SELL) or \
                           (position.side == "SHORT" and latest_signal.action == ActionType.BUY):
                            should_close = True
                            exit_reason = "SIGNAL"
                            logger.info(f"Opposite signal detected for {position.pair}")
                
                # CLOSE POSITION
                if should_close and exit_reason:
                    await self.close_position(position, current_price, exit_reason)
            
            except Exception as e:
                logger.error(f"Error monitoring position {position.position_id}: {e}")
    
    async def close_position(self, position: Position, exit_price: float, reason: str):
        """Close position and record trade."""
        try:
            logger.info(f"CLOSING position {position.pair} @ ${exit_price:.2f} (reason: {reason})")
            
            # Close on exchange
            success = exchange.close_position(position.pair)
            if not success:
                logger.error("Failed to close position on exchange")
                return
            
            # Calculate PnL
            if position.side == "LONG":
                pnl = (exit_price - position.entry_price) * position.quantity
            else:  # SHORT
                pnl = (position.entry_price - exit_price) * position.quantity
            
            pnl_percent = (pnl / position.size) * 100 if position.size > 0 else 0
            
            # Fees (estimated 0.04% taker)
            fees = position.size * 0.0004 * 2  # open + close
            pnl_net = pnl - fees
            
            # Create Trade object
            duration = (datetime.now() - position.opened_at).total_seconds() / 60
            
            trade = Trade(
                trade_id=str(uuid.uuid4()),
                position_id=position.position_id,
                pair=position.pair,
                side=position.side,
                entry_price=position.entry_price,
                exit_price=exit_price,
                size=position.size,
                quantity=position.quantity,
                pnl=pnl_net,
                pnl_percent=pnl_percent,
                fees=fees,
                opened_at=position.opened_at,
                closed_at=datetime.now(),
                duration_minutes=int(duration),
                exit_reason=reason
            )
            
            # Save trade
            db.save_trade(trade)
            
            # Remove position from active
            db.close_position(position.position_id)
            
            # Update capital
            new_capital = db.get_current_capital() + pnl_net
            db.update_capital(new_capital)
            
            emoji = "💰" if pnl_net > 0 else "📉"
            logger.success(f"{emoji} Position closed: PnL ${pnl_net:.2f} ({pnl_percent:+.2f}%)")
            
            # Telegram notification
            await telegram_notifier.send_message(f"""
{emoji} <b>POSITION CLOSED</b>

{position.side} {position.pair}
Entry: ${position.entry_price:.2f}
Exit: ${exit_price:.2f}

PnL: <b>${pnl_net:.2f}</b> ({pnl_percent:+.2f}%)
Duration: {int(duration)} min
Reason: {reason}

New Balance: ${new_capital:.2f}
""")
        
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            import traceback
            traceback.print_exc()
