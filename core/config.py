from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Anthropic API Key (used by CrewAI via LiteLLM)
    anthropic_api_key: str = ""

    # CrewAI / LLM
    crew_model: str = "claude-sonnet-4-20250514"
    crew_temperature: float = 0.3
    crew_max_tokens: int = 4000
    crew_verbose: bool = False

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
    risk_per_trade: float = 0.02
    max_positions: int = 3
    max_drawdown: float = 0.20
    trading_pairs: str = "BTC/USDT,ETH/USDT"

    # Strategy
    strategy_interval_minutes: int = 30
    execution_interval_seconds: int = 30

    # Logging
    log_level: str = "INFO"
    sentry_dsn: str = ""

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Cost monitoring
    daily_cost_limit_usd: float = 5.0
    monthly_cost_limit_usd: float = 150.0

    # Safeguards
    max_trades_per_day: int = 8
    min_position_spacing_minutes: int = 90
    consecutive_loss_pause_count: int = 3
    consecutive_loss_pause_hours: int = 2
    max_capital_in_positions_pct: float = 0.10
    min_confidence: int = 60
    full_size_confidence: int = 70
    min_rr_ratio: float = 2.0
    max_sl_distance_pct: float = 3.0
    max_spread_bps: int = 10
    max_slippage_pct: float = 0.5

    @property
    def pairs_list(self) -> List[str]:
        """Convert comma-separated pairs string to list."""
        return [p.strip() for p in self.trading_pairs.split(",")]

    @property
    def crew_llm_string(self) -> str:
        """LLM identifier string for CrewAI (LiteLLM format)."""
        return f"anthropic/{self.crew_model}"

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


settings = Settings()
