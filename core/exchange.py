from binance.client import Client
from binance.exceptions import BinanceAPIException
from typing import Dict, List, Optional
from loguru import logger
from core.config import settings


class BinanceExchangeWrapper:
    """Wrapper for Binance API with testnet/mainnet support."""
    
    def __init__(self):
        self.testnet = settings.binance_testnet
        
        if self.testnet:
            self.client = Client(
                settings.binance_api_key,
                settings.binance_secret_key,
                testnet=True
            )
            self.base_url = "https://testnet.binancefuture.com"
            logger.info("Binance TESTNET connected")
        else:
            self.client = Client(
                settings.binance_api_key,
                settings.binance_secret_key
            )
            self.base_url = "https://fapi.binance.com"
            logger.warning("Binance MAINNET connected - REAL MONEY")
    
    def get_account_balance(self) -> float:
        """Get USDT balance."""
        try:
            balance = self.client.futures_account_balance()
            usdt_balance = next((b for b in balance if b['asset'] == 'USDT'), None)
            return float(usdt_balance['balance']) if usdt_balance else 0.0
        except BinanceAPIException as e:
            logger.error(f"Error fetching balance: {e}")
            return 0.0
    
    def get_current_price(self, symbol: str) -> float:
        """Get current price for symbol."""
        try:
            # Convert BTC/USDT → BTCUSDT
            symbol_clean = symbol.replace("/", "")
            ticker = self.client.futures_symbol_ticker(symbol=symbol_clean)
            return float(ticker['price'])
        except BinanceAPIException as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
            return 0.0
    
    def get_klines(self, symbol: str, interval: str, limit: int = 500) -> List[Dict]:
        """Get OHLCV klines.
        
        Args:
            symbol: e.g. "BTC/USDT"
            interval: e.g. "1m", "5m", "15m", "1h", "4h"
            limit: number of candles (max 1500)
        """
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
            return []
    
    def place_market_order(
        self,
        symbol: str,
        side: str,  # "BUY" or "SELL"
        quantity: float
    ) -> Optional[Dict]:
        """Place market order."""
        try:
            symbol_clean = symbol.replace("/", "")
            
            # Round quantity to appropriate precision
            quantity = round(quantity, 6)
            
            order = self.client.futures_create_order(
                symbol=symbol_clean,
                side=side,
                type="MARKET",
                quantity=quantity
            )
            
            logger.info(f"Order placed: {side} {quantity} {symbol} @ MARKET")
            return order
        except BinanceAPIException as e:
            logger.error(f"Error placing order: {e}")
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
                quantity=round(quantity, 6),
                price=round(price, 2)
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
            self.client.futures_change_leverage(symbol=symbol_clean, leverage=leverage)
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
                        "unrealized_pnl": float(pos['unRealizedProfit']),
                        "leverage": int(pos['leverage'])
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
