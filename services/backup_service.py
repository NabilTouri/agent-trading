import asyncio
import os
import json
from datetime import datetime, timedelta
from loguru import logger
from core.database import db
from core.exchange import exchange
from core.config import settings
from services.telegram_bot import telegram_notifier
    

class BackupService:
    """Daily backup of Redis to JSON files and Telegram."""

    def __init__(self):
        self.backup_dir = "/app/backups"
        os.makedirs(self.backup_dir, exist_ok=True)

    async def run(self):
        """Main loop: backup daily at 3 AM."""
        logger.info("Backup service started")

        while True:
            try:
                now = datetime.now()

                # Execute backup at 3 AM
                if now.hour == 3 and now.minute == 0:
                    await self.create_backup()
                    await asyncio.sleep(3600)  # Sleep 1h to avoid duplicate backups

                await asyncio.sleep(60)  # Check every minute

            except Exception as e:
                logger.error(f"Backup service error: {e}")
                await asyncio.sleep(300)

    async def create_backup(self):
        """Create Redis backup JSON and send summary to Telegram."""
        try:
            logger.info("Creating backup...")

            # Trigger Redis save
            db.client.save()
            await asyncio.sleep(5)

            # Collect all data
            metrics = db.calculate_metrics()
            capital = exchange.get_account_balance()
            initial_capital = db.get_initial_capital()
            positions = db.get_all_open_positions()
            trades = db.get_trades_history(limit=500)

            # Collect signals for all pairs
            signals = {}
            for pair in settings.pairs_list:
                signals[pair] = db.get_signals_history(pair, limit=100)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Create backup data structure
            backup_data = {
                "timestamp": datetime.now().isoformat(),
                "capital": {
                    "initial": initial_capital,
                    "current": capital,
                    "pnl": capital - initial_capital if initial_capital > 0 else 0,
                    "roi_percent": ((capital - initial_capital) / initial_capital * 100) if initial_capital > 0 else 0
                },
                "metrics": metrics,
                "positions": [pos.model_dump() for pos in positions],
                "trades": [trade.model_dump() for trade in trades],
                "signals": {
                    pair: [sig.model_dump() for sig in sigs]
                    for pair, sigs in signals.items()
                },
                "config": {
                    "pairs": settings.pairs_list,
                    "risk_per_trade": settings.risk_per_trade,
                    "max_positions": settings.max_positions,
                    "testnet": settings.binance_testnet
                }
            }

            # Save to JSON file
            filename = f"backup_{timestamp}.json"
            filepath = os.path.join(self.backup_dir, filename)

            with open(filepath, 'w') as f:
                json.dump(backup_data, f, indent=2, default=str)

            logger.info(f"Backup saved to {filename}")

            # Cleanup old backups (keep last 30 days)
            self._cleanup_old_backups()

            # Create summary message
            summary = f"""📦 <b>Daily Backup - {datetime.now().strftime('%Y-%m-%d')}</b>

💰 Capital: ${capital:.2f}
📊 Total Trades: {metrics['total_trades']}
🎯 Win Rate: {metrics['win_rate']}%
💵 Total PnL: ${metrics['total_pnl']:.2f}
📈 ROI: {backup_data['capital']['roi_percent']:.2f}%

📍 Open Positions: {len(positions)}
💾 Backup saved: {filename}
"""

            await telegram_notifier.send_message(summary)

            # Send backup file as document to Telegram
            await telegram_notifier.send_document(
                filepath,
                caption=f"Backup {datetime.now().strftime('%Y-%m-%d')}"
            )

            logger.success("Backup completed")

        except Exception as e:
            logger.error(f"Backup failed: {e}")
            await telegram_notifier.send_message(f"❌ Backup failed: {str(e)}")

    def _cleanup_old_backups(self):
        """Delete backups older than 30 days."""
        try:
            cutoff_date = datetime.now() - timedelta(days=30)

            for filename in os.listdir(self.backup_dir):
                if not filename.startswith("backup_") or not filename.endswith(".json"):
                    continue

                filepath = os.path.join(self.backup_dir, filename)
                file_time = datetime.fromtimestamp(os.path.getmtime(filepath))

                if file_time < cutoff_date:
                    os.remove(filepath)
                    logger.info(f"Deleted old backup: {filename}")

        except Exception as e:
            logger.warning(f"Error during backup cleanup: {e}")


async def main():
    """Main entry point for backup service."""
    service = BackupService()
    await service.run()


if __name__ == "__main__":
    asyncio.run(main())
