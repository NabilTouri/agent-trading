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
        self.consecutive_losses = 0
        self.daily_trades_count = 0
        self.last_reset_date = datetime.now().date()
        self._paused = False
        self._attempted_signals: set = set()  # Track signals already attempted
        logger.info(f"ExecutionLoop initialized (interval: {self.interval}s)")

    def _calculate_drawdown(self) -> float:
        """Calculate current drawdown percentage."""
        current_capital = exchange.get_account_balance()
        initial_capital = db.get_initial_capital()

        if initial_capital == 0 or current_capital >= initial_capital:
            return 0.0

        return ((initial_capital - current_capital) / initial_capital) * 100

    async def run(self):
        """Main loop."""
        # Initial delay
        await asyncio.sleep(10)

        while True:
            try:
                # Reset daily counter
                if datetime.now().date() != self.last_reset_date:
                    self.daily_trades_count = 0
                    self.last_reset_date = datetime.now().date()

                # CIRCUIT BREAKER 1: Max drawdown
                drawdown = self._calculate_drawdown()
                if drawdown > settings.max_drawdown * 100:  # 20%
                    logger.critical(f"🚨 MAX DRAWDOWN REACHED: {drawdown:.1f}%")
                    await telegram_notifier.send_message(
                        "🚨 <b>EMERGENCY STOP</b>\n\n"
                        f"Max drawdown exceeded: {drawdown:.1f}%\n"
                        "Bot paused. Manual intervention required."
                    )
                    await asyncio.sleep(3600)  # Sleep 1h
                    continue

                # CIRCUIT BREAKER 2: Consecutive losses
                if self.consecutive_losses >= 3:
                    logger.warning("⚠️ 3 consecutive losses - cooling off 1h")
                    await telegram_notifier.send_message(
                        "⚠️ <b>COOLING OFF</b>\n\n"
                        "3 consecutive losses detected.\n"
                        "Pausing trading for 1 hour."
                    )
                    await asyncio.sleep(3600)
                    self.consecutive_losses = 0
                    continue

                # CIRCUIT BREAKER 3: Daily trade limit
                if self.daily_trades_count >= 10:
                    logger.warning("⚠️ Daily trade limit reached (10)")
                    await asyncio.sleep(300)
                    continue

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
                # Clean up old attempted signal IDs for this pair
                self._attempted_signals.discard(signal.signal_id)
                continue

            # Skip signals already attempted (success or failure)
            if signal.signal_id in self._attempted_signals:
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

            # Mark signal as attempted BEFORE execution (prevents retry on failure)
            self._attempted_signals.add(signal.signal_id)

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

            # Determine side early for stop_loss fallback
            position_side = "LONG" if signal.action == ActionType.BUY else "SHORT"

            # FIX: Validate stop_loss — if 0 or missing, calculate fallback
            if stop_loss <= 0:
                if position_side == "LONG":
                    stop_loss = round(current_price * 0.97, 2)  # 3% below entry
                else:
                    stop_loss = round(current_price * 1.03, 2)  # 3% above entry
                logger.warning(
                    f"⚠️ Stop loss was 0 — using fallback: ${stop_loss:.2f} "
                    f"(3% {'below' if position_side == 'LONG' else 'above'} entry)"
                )

            # Enforce Binance minimum notional (100 USDT)
            MIN_NOTIONAL = 100.0
            if position_size < MIN_NOTIONAL:
                logger.warning(
                    f"Position size ${position_size:.2f} below minimum notional "
                    f"${MIN_NOTIONAL:.0f}, adjusting to minimum"
                )
                position_size = MIN_NOTIONAL

            # SLIPPAGE PROTECTION
            expected_price = signal.market_data.get('price')
            if expected_price and expected_price > 0:
                slippage_pct = abs(current_price - expected_price) / expected_price * 100

                if slippage_pct > 0.5:  # 0.5% max slippage
                    logger.warning(
                        f"⚠️ High slippage detected: {slippage_pct:.2f}% "
                        f"(expected ${expected_price:.2f}, got ${current_price:.2f})"
                    )
                    await telegram_notifier.send_message(
                        f"⚠️ <b>Trade aborted</b> — slippage too high: {slippage_pct:.2f}%\n"
                        f"Expected: ${expected_price:.2f}\n"
                        f"Current: ${current_price:.2f}"
                    )
                    return

            # Calculate quantity to buy
            quantity = position_size / current_price

            # Side already determined above for stop_loss fallback
            side = "BUY" if signal.action == ActionType.BUY else "SELL"

            # Place market order
            order = exchange.place_market_order(signal.pair, side, quantity)

            if not order:
                logger.error(f"Order failed for {signal.pair}")
                await telegram_notifier.send_message(
                    f"❌ <b>ORDER FAILED</b>\n\n"
                    f"{signal.action} {signal.pair}\n"
                    f"Quantity: {quantity:.6f}\n"
                    f"The order was rejected by the exchange."
                )
                return

            # FIX: Robustly parse filled quantity and price from order response
            try:
                filled_qty = float(order.get('executedQty', 0))
            except (ValueError, TypeError):
                filled_qty = 0

            if filled_qty <= 0:
                filled_qty = quantity
                logger.warning(f"executedQty missing/zero in order response, using calculated qty: {quantity}")

            try:
                avg_price = float(order.get('avgPrice', 0))
            except (ValueError, TypeError):
                avg_price = 0

            if avg_price <= 0:
                # Fallback: calculate from cumQuote / executedQty
                try:
                    cum_quote = float(order.get('cumQuote', 0))
                except (ValueError, TypeError):
                    cum_quote = 0
                avg_price = cum_quote / filled_qty if filled_qty > 0 and cum_quote > 0 else current_price

            if avg_price <= 0:
                avg_price = current_price
                logger.warning(f"avgPrice still 0 after fallbacks, using current_price: ${current_price}")

            actual_size = filled_qty * avg_price
            logger.info(f"Order fill details: qty={filled_qty}, avg_price=${avg_price:.2f}, size=${actual_size:.2f}")

            # Create Position object
            position = Position(
                position_id=str(uuid.uuid4()),
                pair=signal.pair,
                side=position_side,
                entry_price=avg_price,
                size=actual_size,
                quantity=filled_qty,
                stop_loss=stop_loss,
                take_profit=take_profit,
                opened_at=datetime.now(),
                signal_id=signal.signal_id
            )

            # Save to DB
            db.save_position(position)

            logger.success(
                f"✅ Position opened: {position_side} {filled_qty:.6f} "
                f"{signal.pair} @ ${avg_price:.2f}"
            )

            # Telegram notification
            await telegram_notifier.send_message(f"""
✅ <b>POSITION OPENED</b>

{position_side} {signal.pair}
Entry: ${avg_price:.2f}
Size: ${actual_size:.2f}
Quantity: {filled_qty:.6f}
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

                # FIX: Only check Stop Loss if stop_loss is set (> 0)
                if position.stop_loss > 0:
                    if position.side == "LONG" and current_price <= position.stop_loss:
                        should_close = True
                        exit_reason = "SL"
                        logger.warning(f"Stop Loss hit for {position.pair} @ ${current_price:.2f} (<= SL ${position.stop_loss:.2f})")

                    elif position.side == "SHORT" and current_price >= position.stop_loss:
                        should_close = True
                        exit_reason = "SL"
                        logger.warning(f"Stop Loss hit for {position.pair} @ ${current_price:.2f} (>= SL ${position.stop_loss:.2f})")
                else:
                    logger.warning(f"⚠️ Position {position.pair} has stop_loss=0 — no SL protection!")

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

            # Track consecutive losses for circuit breaker
            if pnl_net < 0:
                self.consecutive_losses += 1
            else:
                self.consecutive_losses = 0

            self.daily_trades_count += 1

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

            # Get updated balance from broker
            new_balance = exchange.get_account_balance()
            db.save_daily_snapshot(new_balance)

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

New Balance: ${new_balance:.2f}
""")

        except Exception as e:
            logger.error(f"Error closing position: {e}")
            import traceback
            traceback.print_exc()