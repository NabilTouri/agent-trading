import asyncio
import sys
from loguru import logger
from core.config import settings
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


async def main():
    """Main entry point for the trading bot."""
    logger.info("=" * 50)
    logger.info("AI TRADING BOT STARTING")
    logger.info(f"Mode: {'TESTNET' if settings.binance_testnet else 'MAINNET'}")
    logger.info(f"Trading Pairs: {settings.pairs_list}")
    logger.info(f"Initial Capital: ${settings.initial_capital}")
    logger.info(f"Risk per Trade: {settings.risk_per_trade * 100}%")
    logger.info(f"Max Positions: {settings.max_positions}")
    logger.info("=" * 50)
    
    # Send startup notification
    await telegram_notifier.send_message(
        f"""🤖 <b>Trading Bot Started</b>

Mode: {'TESTNET' if settings.binance_testnet else '⚠️ MAINNET'}
Pairs: {', '.join(settings.pairs_list)}
Capital: ${settings.initial_capital}
Risk/Trade: {settings.risk_per_trade * 100}%"""
    )
    
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
