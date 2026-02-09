from telegram import Bot
from telegram.error import TelegramError
from loguru import logger
from core.config import settings
import asyncio


class TelegramNotifier:
    """Telegram notification service for alerts."""
    
    def __init__(self):
        self._bot = None
        self.chat_id = settings.telegram_chat_id
        self._initialized = False
        
        if settings.telegram_bot_token and settings.telegram_chat_id:
            try:
                self._bot = Bot(token=settings.telegram_bot_token)
                self._initialized = True
                logger.info("Telegram bot initialized")
            except Exception as e:
                logger.warning(f"Telegram bot initialization failed: {e}")
        else:
            logger.warning("Telegram bot not configured (token/chat_id missing)")
    
    @property
    def bot(self):
        return self._bot
    
    async def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send message to Telegram."""
        if not self._initialized:
            logger.debug(f"Telegram not configured, message not sent: {text[:50]}...")
            return False
        
        try:
            await self._bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode=parse_mode
            )
            return True
        except TelegramError as e:
            logger.error(f"Error sending Telegram message: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending Telegram message: {e}")
            return False
    
    async def send_document(self, document_path: str, caption: str = "") -> bool:
        """Send document to Telegram."""
        if not self._initialized:
            return False
        
        try:
            with open(document_path, 'rb') as f:
                await self._bot.send_document(
                    chat_id=self.chat_id,
                    document=f,
                    caption=caption
                )
            return True
        except Exception as e:
            logger.error(f"Error sending Telegram document: {e}")
            return False
    
    def send_message_sync(self, text: str) -> bool:
        """Synchronous wrapper for sending message."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're in an async context, create a task
                asyncio.create_task(self.send_message(text))
                return True
            else:
                return loop.run_until_complete(self.send_message(text))
        except RuntimeError:
            # No event loop, create one
            return asyncio.run(self.send_message(text))


# Singleton instance
telegram_notifier = TelegramNotifier()
