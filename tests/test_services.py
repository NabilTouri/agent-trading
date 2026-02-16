"""
Tests for services — TelegramNotifier and BackupService.
All external calls are mocked.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock


class TestTelegramNotifier:
    """Tests for TelegramNotifier with mocked Bot."""

    def _make_notifier(self, initialized=True):
        from services.telegram_bot import TelegramNotifier

        with patch.object(TelegramNotifier, "__init__", lambda self: None):
            notifier = TelegramNotifier()
            notifier._bot = MagicMock() if initialized else None
            notifier._initialized = initialized
            notifier.chat_id = "12345"
        return notifier

    @pytest.mark.asyncio
    async def test_send_message_not_configured(self):
        """Should return False if bot is not initialized."""
        notifier = self._make_notifier(initialized=False)
        result = await notifier.send_message("test")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_success(self):
        """Should send message and return True."""
        notifier = self._make_notifier()
        notifier._bot.send_message = AsyncMock()
        result = await notifier.send_message("Hello!")
        assert result is True
        notifier._bot.send_message.assert_called_once_with(
            chat_id="12345",
            text="Hello!",
            parse_mode="HTML",
        )

    @pytest.mark.asyncio
    async def test_send_message_telegram_error(self):
        """Should handle TelegramError gracefully."""
        from telegram.error import TelegramError

        notifier = self._make_notifier()
        notifier._bot.send_message = AsyncMock(side_effect=TelegramError("fail"))
        result = await notifier.send_message("will fail")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_document_not_configured(self):
        """Should return False if not initialized."""
        notifier = self._make_notifier(initialized=False)
        result = await notifier.send_document("/path/to/file")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_document_success(self, tmp_path):
        """Should send a file document."""
        notifier = self._make_notifier()
        notifier._bot.send_document = AsyncMock()

        # Create a temp file
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        result = await notifier.send_document(str(test_file), caption="test")
        assert result is True


class TestBackupService:
    """Tests for BackupService with mocked DB and Telegram."""

    @pytest.mark.asyncio
    async def test_create_backup(self):
        """Should trigger Redis save, get metrics, and send Telegram summary."""
        with patch("services.backup_service.db") as mock_db, \
             patch("services.backup_service.exchange") as mock_ex, \
             patch("services.backup_service.telegram_notifier") as mock_tg, \
             patch("services.backup_service.settings") as mock_settings, \
             patch("builtins.open", create=True) as mock_open:

            mock_db.client.save.return_value = True
            mock_db.calculate_metrics.return_value = {
                "total_trades": 42,
                "win_rate": 65.0,
                "total_pnl": 150.0,
            }
            mock_ex.get_account_balance.return_value = 3150.0
            mock_db.get_initial_capital.return_value = 3000.0
            mock_db.get_all_open_positions.return_value = []
            mock_db.get_trades_history.return_value = []
            mock_db.get_signals_history.return_value = []
            mock_settings.pairs_list = ["BTC/USDT", "ETH/USDT"]
            mock_settings.risk_per_trade = 0.02
            mock_settings.max_positions = 3
            mock_settings.binance_testnet = True
            mock_tg.send_message = AsyncMock()
            mock_tg.send_document = AsyncMock()

            from services.backup_service import BackupService
            service = BackupService()
            await service.create_backup()

            mock_db.client.save.assert_called_once()
            mock_tg.send_message.assert_called_once()
            msg = mock_tg.send_message.call_args[0][0]
            assert "$3150.00" in msg
            assert "42" in msg
            mock_tg.send_document.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_backup_error(self):
        """Should handle errors and notify via Telegram."""
        with patch("services.backup_service.db") as mock_db, \
             patch("services.backup_service.telegram_notifier") as mock_tg:

            mock_db.client.save.side_effect = Exception("Redis down")
            mock_tg.send_message = AsyncMock()

            from services.backup_service import BackupService
            service = BackupService()
            await service.create_backup()

            # Should have sent error message
            assert mock_tg.send_message.call_count >= 1
