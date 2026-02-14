import asyncio
import sys
from loguru import logger
from core.config import settings
from core.database import db
from core.exchange import exchange
from bot.strategy_loop import StrategyLoop
from bot.execution_loop import ExecutionLoop
from services.telegram_bot import telegram_notifier

# Configure logging
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
    level=settings.log_level
)
logger.add(
    "logs/bot_{time}.log",
    rotation="1 day",
    retention="30 days",
    level="DEBUG"
)


async def reconcile_positions():
    """Synchronize Redis positions with Binance at startup."""
    logger.info("🔄 Reconciling positions with Binance...")

    try:
        # Positions in Redis
        redis_positions = db.get_all_open_positions()
        reconciled = 0

        for pair in settings.pairs_list:
            try:
                # Real position on Binance
                binance_pos = exchange.get_position_info(pair)

                # Find matching Redis position
                redis_pos = next((p for p in redis_positions if p.pair == pair), None)

                # CASE 1: Position on Binance but not in Redis (orphan)
                if binance_pos and not redis_pos:
                    logger.warning(f"⚠️ Orphan position on Binance: {pair} "
                                   f"({binance_pos['side']} {binance_pos['quantity']})")
                    success = exchange.close_position(pair)
                    if success:
                        await telegram_notifier.send_message(
                            f"🔄 <b>Reconciliation</b>\n\n"
                            f"Closed orphan position on Binance: {pair}\n"
                            f"Side: {binance_pos['side']}, Qty: {binance_pos['quantity']}"
                        )
                        reconciled += 1
                    else:
                        logger.error(f"❌ Failed to close orphan position: {pair}")

                # CASE 2: Position in Redis but not on Binance (stale)
                elif redis_pos and not binance_pos:
                    logger.warning(f"⚠️ Stale position in Redis: {pair} "
                                   f"(ID: {redis_pos.position_id})")
                    db.close_position(redis_pos.position_id)
                    await telegram_notifier.send_message(
                        f"🔄 <b>Reconciliation</b>\n\n"
                        f"Removed stale position from Redis: {pair}\n"
                        f"ID: {redis_pos.position_id}"
                    )
                    reconciled += 1

            except Exception as e:
                logger.error(f"❌ Reconciliation error for {pair}: {e}")

        if reconciled > 0:
            logger.warning(f"🔄 Reconciled {reconciled} position(s)")
        else:
            logger.success("✅ Position reconciliation complete — no discrepancies")

    except Exception as e:
        logger.error(f"❌ Position reconciliation failed: {e}")
        await telegram_notifier.send_message(
            f"⚠️ <b>Reconciliation failed</b>\n\nError: {str(e)}"
        )


async def main():
    """Main entry point for the trading bot."""
    # Get current balance from Binance
    current_balance = exchange.get_account_balance()

    logger.info("=" * 50)
    logger.info("AI TRADING BOT STARTING")
    logger.info(f"Mode: {'TESTNET' if settings.binance_testnet else 'MAINNET'}")
    logger.info(f"Trading Pairs: {settings.pairs_list}")
    logger.info(f"Current Balance: ${current_balance:.2f}")
    logger.info(f"Risk per Trade: {settings.risk_per_trade * 100}%")
    logger.info(f"Max Positions: {settings.max_positions}")
    logger.info("=" * 50)

    # Send startup notification
    await telegram_notifier.send_message(
        f"""🤖 <b>Trading Bot Started</b>

Mode: {'TESTNET' if settings.binance_testnet else '⚠️ MAINNET'}
Pairs: {', '.join(settings.pairs_list)}
Balance: ${current_balance:.2f}
Risk/Trade: {settings.risk_per_trade * 100}%"""
    )

    # Reconcile positions before starting loops
    await reconcile_positions()

    # Initialize loops
    strategy = StrategyLoop()
    execution = ExecutionLoop()

    try:
        # Run loops in parallel
        await asyncio.gather(
            strategy.run(),
            execution.run()
        )
    except KeyboardInterrupt:
        logger.warning("Bot stopped by user")
        await telegram_notifier.send_message("🛑 Trading Bot stopped manually")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        await telegram_notifier.send_message(f"❌ Bot crashed: {str(e)}")
        raise


if __name__ == "__main__":
    asyncio.run(main())