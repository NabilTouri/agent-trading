import asyncio
import os
from datetime import datetime
from loguru import logger
from core.database import db
from core.exchange import exchange
from services.telegram_bot import telegram_notifier


class BackupService:
    """Daily backup of Redis to Telegram."""
    
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
        """Create Redis backup and send to Telegram."""
        try:
            logger.info("Creating backup...")
            
            # Trigger Redis save
            db.client.save()
            
            # Wait for save to complete
            await asyncio.sleep(5)
            
            # Create metrics backup
            metrics = db.calculate_metrics()
            capital = exchange.get_account_balance()
            positions = db.get_all_open_positions()
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Create summary message
            summary = f"""
📦 <b>Daily Backup - {datetime.now().strftime('%Y-%m-%d')}</b>

💰 Capital: ${capital:.2f}
📊 Total Trades: {metrics['total_trades']}
🎯 Win Rate: {metrics['win_rate']}%
💵 Total PnL: ${metrics['total_pnl']:.2f}

📍 Open Positions: {len(positions)}
"""
            
            await telegram_notifier.send_message(summary)
            
            logger.success("Backup completed and sent to Telegram")
        
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            await telegram_notifier.send_message(f"❌ Backup failed: {str(e)}")


async def main():
    """Main entry point for backup service."""
    service = BackupService()
    await service.run()


if __name__ == "__main__":
    asyncio.run(main())
