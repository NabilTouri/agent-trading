#!/usr/bin/env python3
"""
Seed Data Script
Populates Redis with initial data from broker.
"""

import sys
sys.path.insert(0, '/app')

from loguru import logger
from core.config import settings
from core.database import db
from core.exchange import exchange


def main():
    """Seed initial data from broker."""
    logger.info("=" * 50)
    logger.info("SEED DATA")
    logger.info("=" * 50)
    
    # Get balance from broker
    broker_balance = exchange.get_account_balance()
    logger.info(f"Broker balance: ${broker_balance:.2f}")
    
    # Save as initial capital
    db.save_initial_capital(broker_balance)
    
    # Verify
    initial = db.get_initial_capital()
    logger.success(f"✅ Initial capital set to: ${initial:.2f}")
    
    logger.info("=" * 50)
    logger.success("Data seeding complete!")
    
    return 0


if __name__ == "__main__":
    exit(main())
