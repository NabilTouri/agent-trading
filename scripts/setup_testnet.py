#!/usr/bin/env python3
"""
Setup Testnet Script
Verifies connections to all services before starting the bot.
"""

import sys
sys.path.insert(0, '/app')

from loguru import logger
from core.config import settings


def check_redis():
    """Check Redis connection."""
    logger.info("Checking Redis connection...")
    try:
        from core.database import db
        db.client.ping()
        logger.success("✅ Redis connected")
        return True
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {e}")
        return False


def check_binance():
    """Check Binance connection."""
    logger.info("Checking Binance connection...")
    try:
        from core.exchange import exchange
        balance = exchange.get_account_balance()
        logger.success(f"✅ Binance connected - Balance: ${balance:.2f} USDT")
        return True
    except Exception as e:
        logger.error(f"❌ Binance connection failed: {e}")
        return False


def check_price_feed():
    """Check price feed."""
    logger.info("Checking price feed...")
    try:
        from core.exchange import exchange
        for pair in settings.pairs_list:
            price = exchange.get_current_price(pair)
            if price > 0:
                logger.success(f"✅ {pair}: ${price:.2f}")
            else:
                logger.warning(f"⚠️ {pair}: Could not fetch price")
        return True
    except Exception as e:
        logger.error(f"❌ Price feed failed: {e}")
        return False


def check_anthropic():
    """Check Anthropic API key is configured."""
    logger.info("Checking Anthropic API key...")
    if settings.anthropic_api_key and len(settings.anthropic_api_key) > 10:
        logger.success("✅ Anthropic API key configured")
        return True
    else:
        logger.error("❌ Anthropic API key not configured")
        return False


def check_telegram():
    """Check Telegram configuration."""
    logger.info("Checking Telegram configuration...")
    if settings.telegram_bot_token and settings.telegram_chat_id:
        logger.success("✅ Telegram configured")
        return True
    else:
        logger.warning("⚠️ Telegram not configured (optional)")
        return True  # Optional, don't fail


def main():
    """Run all checks."""
    logger.info("=" * 50)
    logger.info("SETUP TESTNET - VERIFICATION")
    logger.info(f"Mode: {'TESTNET' if settings.binance_testnet else 'MAINNET'}")
    logger.info(f"Trading Pairs: {settings.pairs_list}")
    logger.info("=" * 50)
    
    checks = [
        ("Redis", check_redis),
        ("Binance", check_binance),
        ("Price Feed", check_price_feed),
        ("Anthropic", check_anthropic),
        ("Telegram", check_telegram),
    ]
    
    results = []
    for name, check_fn in checks:
        try:
            results.append((name, check_fn()))
        except Exception as e:
            logger.error(f"Check {name} raised exception: {e}")
            results.append((name, False))
    
    # Summary
    logger.info("=" * 50)
    logger.info("SUMMARY")
    logger.info("=" * 50)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    logger.info("=" * 50)
    
    if all_passed:
        logger.success("✅ ALL CHECKS PASSED - Ready to trade!")
        return 0
    else:
        logger.error("❌ SOME CHECKS FAILED - Fix issues before trading")
        return 1


if __name__ == "__main__":
    exit(main())
