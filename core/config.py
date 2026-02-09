from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Anthropic
    anthropic_api_key: str = ""
    
    # Binance
    binance_api_key: str = ""
    binance_secret_key: str = ""
    binance_testnet: bool = True
    
    # Redis
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""
    
    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    
    # Trading
    initial_capital: float = 3000.0
    risk_per_trade: float = 0.02
    max_positions: int = 3
    max_drawdown: float = 0.20
    trading_pairs: str = "BTC/USDT,ETH/USDT"
    
    # Strategy
    strategy_interval_minutes: int = 30
    execution_interval_seconds: int = 10
    
    # Logging
    log_level: str = "INFO"
    sentry_dsn: str = ""
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    @property
    def pairs_list(self) -> List[str]:
        """Convert comma-separated pairs string to list."""
        return [p.strip() for p in self.trading_pairs.split(",")]
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
