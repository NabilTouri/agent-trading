#!/usr/bin/env python3
"""
Seed Data Script
Populates Redis with initial data for testing.
"""

import sys
sys.path.insert(0, '/app')

from loguru import logger
from core.config import settings
from core.database import db


def main():
    """Seed initial data."""
    logger.info("=" * 50)
    logger.info("SEED DATA")
    logger.info("=" * 50)
    
    # Initialize capital
    logger.info(f"Setting initial capital: ${settings.initial_capital}")
    db.update_capital(settings.initial_capital)
    
    # Verify
    capital = db.get_current_capital()
    logger.success(f"✅ Capital set to: ${capital}")
    
    logger.info("=" * 50)
    logger.success("Data seeding complete!")
    
    return 0


if __name__ == "__main__":
    exit(main())
