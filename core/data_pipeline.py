from typing import Dict, Any, List
import pandas as pd
import ta
from loguru import logger
from core.exchange import exchange
from core.database import db


class DataPipeline:
    """Fetcher + feature engineering for market data (Phase 1 - no news)."""
    
    async def fetch_market_data(self, pair: str) -> Dict[str, Any]:
        """Fetch all data needed for agents (no news in Phase 1)."""
        logger.debug(f"Fetching market data for {pair}")
        
        try:
            # 1. Fetch candles multiframe
            candles_15m = self._fetch_and_cache_candles(pair, "15m", 100)
            candles_1h = self._fetch_and_cache_candles(pair, "1h", 100)
            candles_4h = self._fetch_and_cache_candles(pair, "4h", 50)
            
            # 2. Current price
            current_price = exchange.get_current_price(pair)
            
            # 3. Calculate indicators (use 1h)
            indicators = self._calculate_indicators(candles_1h)
            
            # 4. Calculate price changes
            changes = self._calculate_changes(candles_1h)
            
            return {
                'pair': pair,
                'current_price': current_price,
                'candles_15m': candles_15m,
                'candles_1h': candles_1h,
                'candles_4h': candles_4h,
                'indicators': indicators,
                # NO 'news' in Phase 1
                'change_1h': changes['1h'],
                'change_4h': changes['4h'],
                'change_24h': changes['24h'],
                'volume_24h': self._calculate_volume_24h(candles_1h),
                'atr': indicators['atr'],
                'volatility': self._calculate_volatility(candles_1h),
                # NO sentiment indicators in Phase 1
                'risk_per_trade': 0.02,
                'entry_price': current_price
            }
        
        except Exception as e:
            logger.error(f"Error fetching market data for {pair}: {e}")
            raise
    
    def _fetch_and_cache_candles(self, pair: str, timeframe: str, limit: int) -> List[Dict]:
        """Fetch candles from exchange and cache in Redis."""
        # Check cache first
        cached = db.get_candles(pair, timeframe, limit)
        if len(cached) >= limit // 2:  # Use cache if at least half populated
            return cached[:limit]
        
        # Fetch from exchange
        candles = exchange.get_klines(pair, timeframe, limit)
        
        # Save to cache
        if candles:
            db.save_candles(pair, timeframe, candles)
        
        return candles
    
    def _calculate_indicators(self, candles: List[Dict]) -> Dict[str, float]:
        """Calculate technical indicators on candles."""
        if len(candles) < 20:
            return {
                'rsi': 50.0,
                'macd': 0.0,
                'macd_signal': 0.0,
                'bb_upper': 0.0,
                'bb_lower': 0.0,
                'atr': 0.0
            }
        
        df = pd.DataFrame(candles)
        
        # RSI
        rsi_indicator = ta.momentum.RSIIndicator(df['close'], window=14)
        rsi = rsi_indicator.rsi().iloc[-1]
        
        # MACD
        macd_indicator = ta.trend.MACD(df['close'])
        macd = macd_indicator.macd().iloc[-1]
        macd_signal = macd_indicator.macd_signal().iloc[-1]
        
        # Bollinger Bands
        bb = ta.volatility.BollingerBands(df['close'])
        bb_upper = bb.bollinger_hband().iloc[-1]
        bb_lower = bb.bollinger_lband().iloc[-1]
        
        # ATR (volatility)
        atr = ta.volatility.AverageTrueRange(
            df['high'], df['low'], df['close']
        ).average_true_range().iloc[-1]
        
        return {
            'rsi': round(rsi, 2) if not pd.isna(rsi) else 50.0,
            'macd': round(macd, 2) if not pd.isna(macd) else 0.0,
            'macd_signal': round(macd_signal, 2) if not pd.isna(macd_signal) else 0.0,
            'bb_upper': round(bb_upper, 2) if not pd.isna(bb_upper) else 0.0,
            'bb_lower': round(bb_lower, 2) if not pd.isna(bb_lower) else 0.0,
            'atr': round(atr, 2) if not pd.isna(atr) else 0.0
        }
    
    def _calculate_changes(self, candles: List[Dict]) -> Dict[str, float]:
        """Calculate price percentage changes."""
        if len(candles) < 24:
            return {'1h': 0.0, '4h': 0.0, '24h': 0.0}
        
        current = candles[-1]['close']
        price_1h = candles[-2]['close'] if len(candles) > 1 else current
        price_4h = candles[-5]['close'] if len(candles) > 4 else current
        price_24h = candles[-24]['close'] if len(candles) > 23 else current
        
        return {
            '1h': round(((current - price_1h) / price_1h) * 100, 2) if price_1h else 0.0,
            '4h': round(((current - price_4h) / price_4h) * 100, 2) if price_4h else 0.0,
            '24h': round(((current - price_24h) / price_24h) * 100, 2) if price_24h else 0.0
        }
    
    def _calculate_volume_24h(self, candles: List[Dict]) -> float:
        """Calculate 24h volume."""
        if len(candles) < 24:
            return 0.0
        return sum(c['volume'] for c in candles[-24:])
    
    def _calculate_volatility(self, candles: List[Dict]) -> str:
        """Calculate volatility classification."""
        if len(candles) < 20:
            return "UNKNOWN"
        
        df = pd.DataFrame(candles[-20:])
        std_dev = df['close'].std()
        mean_price = df['close'].mean()
        
        if mean_price == 0:
            return "UNKNOWN"
        
        volatility_pct = (std_dev / mean_price) * 100
        
        if volatility_pct < 2:
            return "LOW"
        elif volatility_pct < 5:
            return "MEDIUM"
        else:
            return "HIGH"
