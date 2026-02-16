from binance.client import Client
from binance.exceptions import BinanceAPIException
from typing import Dict, List, Optional
from loguru import logger
from core.config import settings
import time
import math


class BinanceExchangeWrapper:
    """Wrapper for Binance API with testnet/mainnet support."""

    def __init__(self):
        self._symbol_info_cache: Dict[str, Dict] = {}
        # TTL caches to reduce API call frequency
        self._price_cache: Dict[str, Dict] = {}  # {symbol: {"price": float, "ts": float}}
        self._balance_cache: Dict = {"balance": 0.0, "ts": 0.0}
        self._PRICE_CACHE_TTL = 30    # seconds (was 5)
        self._BALANCE_CACHE_TTL = 300  # seconds (was 60)

        # Rate-limit backoff state
        self._rate_limited_until: float = 0.0  # timestamp until which we skip API calls
        self._backoff_seconds: float = 60.0     # current backoff duration (doubles on repeat)
        self._MAX_BACKOFF = 600.0               # max backoff: 10 minutes

        if settings.binance_testnet:
            self.client = Client(
                settings.binance_api_key,
                settings.binance_secret_key,
                testnet=True
            )
            logger.info("Binance TESTNET client initialized")
        else:
            self.client = Client(
                settings.binance_api_key,
                settings.binance_secret_key
            )
            logger.warning("⚠️ Binance MAINNET client initialized")

        self._load_symbol_info()

    def _is_rate_limited(self) -> bool:
        """Check if we are currently in a rate-limit backoff window."""
        if time.time() < self._rate_limited_until:
            return True
        # If we just exited the window, reset backoff for next time
        if self._rate_limited_until > 0 and time.time() >= self._rate_limited_until:
            self._rate_limited_until = 0.0
            self._backoff_seconds = 60.0  # reset to initial backoff
            logger.info("✅ Rate-limit backoff window expired, resuming API calls")
        return False

    def _handle_rate_limit(self, error: BinanceAPIException):
        """Activate exponential backoff when a rate-limit error is detected."""
        error_code = getattr(error, 'code', 0)
        if error_code == -1003:
            self._rate_limited_until = time.time() + self._backoff_seconds
            logger.warning(
                f"🚫 Rate limited! Backing off for {self._backoff_seconds:.0f}s "
                f"(until {time.strftime('%H:%M:%S', time.localtime(self._rate_limited_until))})"
            )
            # Double backoff for next time, up to max
            self._backoff_seconds = min(self._backoff_seconds * 2, self._MAX_BACKOFF)

    def _load_symbol_info(self):
        """Load and cache symbol precision info from Binance exchange info."""
        try:
            exchange_info = self.client.futures_exchange_info()
            for s in exchange_info.get('symbols', []):
                symbol = s['symbol']
                qty_precision = s.get('quantityPrecision', 3)
                price_precision = s.get('pricePrecision', 2)

                # Also extract step size from LOT_SIZE filter
                step_size = None
                for f in s.get('filters', []):
                    if f['filterType'] == 'LOT_SIZE':
                        step_size = float(f['stepSize'])
                        break

                self._symbol_info_cache[symbol] = {
                    'quantity_precision': qty_precision,
                    'price_precision': price_precision,
                    'step_size': step_size,
                }
            logger.info(f"Loaded exchange info for {len(self._symbol_info_cache)} symbols")
        except Exception as e:
            logger.warning(f"Failed to load exchange info (will use defaults): {e}")

    def _round_quantity(self, symbol: str, quantity: float) -> float:
        """Round quantity to the correct precision for a symbol."""
        symbol_clean = symbol.replace("/", "")
        info = self._symbol_info_cache.get(symbol_clean)

        if info and info.get('step_size'):
            step_size = info['step_size']
            # Truncate (floor) to step size to avoid exceeding precision
            quantity = math.floor(quantity / step_size) * step_size
            # Round to avoid floating point artifacts
            precision = info['quantity_precision']
            quantity = round(quantity, precision)
        else:
            # Fallback: use 3 decimals (safe for BTC/ETH)
            quantity = round(quantity, 3)
            logger.warning(f"No exchange info for {symbol_clean}, using default precision (3)")

        return quantity

    def _round_price(self, symbol: str, price: float) -> float:
        """Round price to the correct precision for a symbol."""
        symbol_clean = symbol.replace("/", "")
        info = self._symbol_info_cache.get(symbol_clean)

        if info:
            return round(price, info['price_precision'])
        return round(price, 2)

    def get_account_balance(self) -> float:
        """Get USDT balance (cached for 300s). Returns stale value during rate-limit."""
        now = time.time()
        if now - self._balance_cache["ts"] < self._BALANCE_CACHE_TTL:
            return self._balance_cache["balance"]
        # If rate-limited, return stale cache instead of hitting API
        if self._is_rate_limited():
            return self._balance_cache["balance"]
        try:
            balances = self.client.futures_account_balance()
            for b in balances:
                if b['asset'] == 'USDT':
                    balance = float(b['balance'])
                    self._balance_cache = {"balance": balance, "ts": now}
                    return balance
            return 0.0
        except BinanceAPIException as e:
            logger.error(f"Error fetching balance: {e}")
            self._handle_rate_limit(e)
            return self._balance_cache["balance"]  # return stale value on error

    def get_current_price(self, symbol: str) -> float:
        """Get current price for symbol (cached for 30s). Returns stale value during rate-limit."""
        now = time.time()
        cached = self._price_cache.get(symbol)
        if cached and now - cached["ts"] < self._PRICE_CACHE_TTL:
            return cached["price"]
        # If rate-limited, return stale cache instead of hitting API
        if self._is_rate_limited():
            return cached["price"] if cached else 0.0
        try:
            symbol_clean = symbol.replace("/", "")
            ticker = self.client.futures_symbol_ticker(symbol=symbol_clean)
            price = float(ticker['price'])
            self._price_cache[symbol] = {"price": price, "ts": now}
            return price
        except BinanceAPIException as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
            self._handle_rate_limit(e)
            # Return stale cached price if available, else 0
            return cached["price"] if cached else 0.0

    def get_klines(self, symbol: str, interval: str, limit: int = 500) -> List[Dict]:
        """Get OHLCV klines.

        Args:
            symbol: e.g. "BTC/USDT"
            interval: e.g. "1m", "5m", "15m", "1h", "4h"
            limit: number of candles (max 1500)
        """
        # If rate-limited, return empty to avoid hitting the API
        if self._is_rate_limited():
            logger.warning(f"Skipping klines for {symbol} — rate-limited")
            return []
        try:
            symbol_clean = symbol.replace("/", "")
            klines = self.client.futures_klines(
                symbol=symbol_clean,
                interval=interval,
                limit=limit
            )

            # Convert to standard format
            candles = []
            for k in klines:
                candles.append({
                    "timestamp": k[0],
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5])
                })

            return candles
        except BinanceAPIException as e:
            logger.error(f"Error fetching klines for {symbol}: {e}")
            self._handle_rate_limit(e)
            return []

    def place_market_order(
        self,
        symbol: str,
        side: str,  # "BUY" or "SELL"
        quantity: float
    ) -> Optional[Dict]:
        """Place market order with retry logic."""
        # Round quantity to correct precision for this symbol
        quantity = self._round_quantity(symbol, quantity)

        if quantity <= 0:
            logger.error(f"❌ Quantity is 0 after rounding for {symbol}, aborting")
            return None

        for attempt in range(3):
            try:
                symbol_clean = symbol.replace("/", "")

                order = self.client.futures_create_order(
                    symbol=symbol_clean,
                    side=side,
                    type="MARKET",
                    quantity=quantity
                )

                logger.info(f"✅ Order executed: {side} {quantity} {symbol} @ MARKET")
                return order

            except BinanceAPIException as e:
                error_msg = str(e).lower()

                # Non-retryable errors
                if "insufficient balance" in error_msg or \
                   "invalid quantity" in error_msg or \
                   "notional" in error_msg or \
                   "precision" in error_msg:
                    logger.error(f"❌ Non-retryable order error: {e}")
                    return None

                if attempt < 2:
                    logger.warning(f"⚠️ Order API error (attempt {attempt + 1}/3): {e}")
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error(f"❌ Order failed after 3 attempts: {e}")
                    return None

            except Exception as e:
                logger.error(f"❌ Unexpected error placing order: {e}")
                return None

        return None

    def place_limit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float
    ) -> Optional[Dict]:
        """Place limit order."""
        try:
            symbol_clean = symbol.replace("/", "")

            order = self.client.futures_create_order(
                symbol=symbol_clean,
                side=side,
                type="LIMIT",
                timeInForce="GTC",
                quantity=self._round_quantity(symbol, quantity),
                price=self._round_price(symbol, price)
            )

            logger.info(f"Limit order placed: {side} {quantity} {symbol} @ {price}")
            return order
        except BinanceAPIException as e:
            logger.error(f"Error placing limit order: {e}")
            return None

    def set_leverage(self, symbol: str, leverage: int) -> bool:
        """Set leverage for symbol."""
        try:
            symbol_clean = symbol.replace("/", "")
            self.client.futures_change_leverage(
                symbol=symbol_clean,
                leverage=leverage
            )
            logger.info(f"Leverage set to {leverage}x for {symbol}")
            return True
        except BinanceAPIException as e:
            logger.error(f"Error setting leverage: {e}")
            return False

    def get_position_info(self, symbol: str) -> Optional[Dict]:
        """Get current position info."""
        try:
            symbol_clean = symbol.replace("/", "")
            positions = self.client.futures_position_information(symbol=symbol_clean)

            for pos in positions:
                if float(pos['positionAmt']) != 0:
                    return {
                        "symbol": pos['symbol'],
                        "side": "LONG" if float(pos['positionAmt']) > 0 else "SHORT",
                        "quantity": abs(float(pos['positionAmt'])),
                        "entry_price": float(pos['entryPrice']),
                        "unrealized_pnl": float(pos.get('unRealizedProfit', 0)),
                        "leverage": int(pos.get('leverage', 1))
                    }

            return None
        except BinanceAPIException as e:
            logger.error(f"Error fetching position: {e}")
            return None

    def close_position(self, symbol: str) -> bool:
        """Close existing position."""
        try:
            pos_info = self.get_position_info(symbol)
            if not pos_info:
                logger.warning(f"No position to close for {symbol}")
                return False

            # Opposite order to close
            side = "SELL" if pos_info['side'] == "LONG" else "BUY"
            quantity = pos_info['quantity']

            order = self.place_market_order(symbol, side, quantity)
            return order is not None
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return False

    def get_open_orders(self, symbol: str) -> List[Dict]:
        """Get open orders for symbol."""
        try:
            symbol_clean = symbol.replace("/", "")
            return self.client.futures_get_open_orders(symbol=symbol_clean)
        except BinanceAPIException as e:
            logger.error(f"Error fetching open orders: {e}")
            return []

    def cancel_all_orders(self, symbol: str) -> bool:
        """Cancel all open orders for symbol."""
        try:
            symbol_clean = symbol.replace("/", "")
            self.client.futures_cancel_all_open_orders(symbol=symbol_clean)
            logger.info(f"All orders cancelled for {symbol}")
            return True
        except BinanceAPIException as e:
            logger.error(f"Error cancelling orders: {e}")
            return False


# Singleton instance
exchange = BinanceExchangeWrapper()