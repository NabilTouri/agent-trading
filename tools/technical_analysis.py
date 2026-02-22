"""
Technical analysis tools for CrewAI agents.

These tools calculate indicators, detect patterns, find S/R zones,
and analyze volume profiles using the existing DataPipeline.
"""

import json
from typing import List, Dict
import pandas as pd
import numpy as np
import ta
from crewai.tools import tool
from loguru import logger


def _get_exchange():
    from core.exchange import exchange
    return exchange


@tool("calculate_indicators")
def calculate_indicators(pair: str, timeframe: str = "1h") -> str:
    """
    Calculate technical indicators for a trading pair on a given timeframe.
    Returns RSI, MACD, Bollinger Bands, ATR, EMA20/50/200, Stochastic,
    ADX, and OBV. Use this for comprehensive technical assessment.
    """
    try:
        ex = _get_exchange()
        candles = ex.get_klines(pair, timeframe, 200)

        if len(candles) < 26:
            return json.dumps({"pair": pair, "error": "Insufficient candle data"})

        df = pd.DataFrame(candles)

        # RSI
        rsi = ta.momentum.RSIIndicator(df["close"], window=14).rsi().iloc[-1]

        # MACD
        macd_ind = ta.trend.MACD(df["close"])
        macd = macd_ind.macd().iloc[-1]
        macd_signal = macd_ind.macd_signal().iloc[-1]
        macd_hist = macd_ind.macd_diff().iloc[-1]

        # Bollinger Bands
        bb = ta.volatility.BollingerBands(df["close"])
        bb_upper = bb.bollinger_hband().iloc[-1]
        bb_lower = bb.bollinger_lband().iloc[-1]
        bb_mid = bb.bollinger_mavg().iloc[-1]
        bb_width = ((bb_upper - bb_lower) / bb_mid * 100) if bb_mid > 0 else 0

        # ATR
        atr = ta.volatility.AverageTrueRange(
            df["high"], df["low"], df["close"]
        ).average_true_range().iloc[-1]

        # EMAs
        ema_20 = df["close"].ewm(span=20).mean().iloc[-1]
        ema_50 = df["close"].ewm(span=50).mean().iloc[-1]
        ema_200 = df["close"].ewm(span=200).mean().iloc[-1] if len(df) >= 200 else None

        # Stochastic
        stoch = ta.momentum.StochasticOscillator(df["high"], df["low"], df["close"])
        stoch_k = stoch.stoch().iloc[-1]
        stoch_d = stoch.stoch_signal().iloc[-1]

        # ADX
        adx_ind = ta.trend.ADXIndicator(df["high"], df["low"], df["close"])
        adx = adx_ind.adx().iloc[-1]

        # Volume
        current_vol = df["volume"].iloc[-1]
        avg_vol_20 = df["volume"].tail(20).mean()
        vol_ratio = current_vol / avg_vol_20 if avg_vol_20 > 0 else 1.0

        current_price = df["close"].iloc[-1]

        def _safe(v):
            return round(float(v), 4) if pd.notna(v) else None

        # Compact result — pre-interpreted signals to minimize tokens
        trend = (
            "STRONG_UP" if ema_200 and current_price > ema_20 > ema_50 > ema_200
            else "UP" if (current_price > ema_50 > ema_200 if ema_200 else current_price > ema_50)
            else "STRONG_DOWN" if ema_200 and current_price < ema_20 < ema_50 < ema_200
            else "DOWN" if current_price < ema_50
            else "SIDEWAYS"
        )

        result = {
            "pair": pair,
            "tf": timeframe,
            "price": _safe(current_price),
            "rsi": _safe(rsi),
            "rsi_sig": "OVERSOLD" if rsi and rsi < 30 else "OVERBOUGHT" if rsi and rsi > 70 else "NEUTRAL",
            "macd_hist": _safe(macd_hist),
            "macd_sig": "BULL" if macd_hist and macd_hist > 0 else "BEAR",
            "bb_width": _safe(bb_width),
            "bb_pos": "ABOVE" if current_price > bb_upper else "BELOW" if current_price < bb_lower else "IN",
            "atr_pct": _safe((atr / current_price * 100) if current_price > 0 else 0),
            "ema20": _safe(ema_20),
            "ema50": _safe(ema_50),
            "ema200": _safe(ema_200),
            "trend": trend,
            "adx": _safe(adx),
            "trend_str": "STRONG" if adx and adx > 25 else "WEAK" if adx and adx < 20 else "MOD",
            "vol_ratio": _safe(vol_ratio),
        }
        return json.dumps(result)

    except Exception as e:
        logger.error(f"Error calculating indicators for {pair}: {e}")
        return json.dumps({"error": str(e), "pair": pair})


@tool("detect_chart_patterns")
def detect_chart_patterns(pair: str) -> str:
    """
    Detect chart patterns on the 1h timeframe for a trading pair.
    Looks for: double top/bottom, higher highs/lower lows, inside bars,
    and engulfing candles. These patterns help identify potential reversals
    and continuations.
    """
    try:
        ex = _get_exchange()
        candles = ex.get_klines(pair, "1h", 100)

        if len(candles) < 20:
            return json.dumps({"pair": pair, "patterns": [], "error": "Insufficient data"})

        df = pd.DataFrame(candles)
        patterns = []

        # --- Higher Highs / Lower Lows (trend structure) ---
        recent_highs = df["high"].tail(20).tolist()
        recent_lows = df["low"].tail(20).tolist()

        # Simple swing detection using 5-candle windows
        swing_highs = []
        swing_lows = []
        for i in range(2, len(recent_highs) - 2):
            if recent_highs[i] > max(recent_highs[i-2:i]) and recent_highs[i] > max(recent_highs[i+1:i+3]):
                swing_highs.append(recent_highs[i])
            if recent_lows[i] < min(recent_lows[i-2:i]) and recent_lows[i] < min(recent_lows[i+1:i+3]):
                swing_lows.append(recent_lows[i])

        if len(swing_highs) >= 2:
            if swing_highs[-1] > swing_highs[-2]:
                patterns.append({"pattern": "HIGHER_HIGH", "significance": "BULLISH"})
            elif swing_highs[-1] < swing_highs[-2]:
                patterns.append({"pattern": "LOWER_HIGH", "significance": "BEARISH"})

        if len(swing_lows) >= 2:
            if swing_lows[-1] > swing_lows[-2]:
                patterns.append({"pattern": "HIGHER_LOW", "significance": "BULLISH"})
            elif swing_lows[-1] < swing_lows[-2]:
                patterns.append({"pattern": "LOWER_LOW", "significance": "BEARISH"})

        # --- Double Top / Double Bottom ---
        if len(swing_highs) >= 2:
            diff_pct = abs(swing_highs[-1] - swing_highs[-2]) / swing_highs[-2] * 100
            if diff_pct < 0.5:
                patterns.append({"pattern": "DOUBLE_TOP", "significance": "BEARISH", "price": round(swing_highs[-1], 2)})

        if len(swing_lows) >= 2:
            diff_pct = abs(swing_lows[-1] - swing_lows[-2]) / swing_lows[-2] * 100
            if diff_pct < 0.5:
                patterns.append({"pattern": "DOUBLE_BOTTOM", "significance": "BULLISH", "price": round(swing_lows[-1], 2)})

        # --- Engulfing candles (last 3 candles) ---
        for i in range(-3, 0):
            if i - 1 < -len(df):
                continue
            prev_open = df["open"].iloc[i - 1]
            prev_close = df["close"].iloc[i - 1]
            curr_open = df["open"].iloc[i]
            curr_close = df["close"].iloc[i]

            if prev_close < prev_open and curr_close > curr_open:
                if curr_open <= prev_close and curr_close >= prev_open:
                    patterns.append({"pattern": "BULLISH_ENGULFING", "significance": "BULLISH", "candle_index": i})

            if prev_close > prev_open and curr_close < curr_open:
                if curr_open >= prev_close and curr_close <= prev_open:
                    patterns.append({"pattern": "BEARISH_ENGULFING", "significance": "BEARISH", "candle_index": i})

        # --- Inside bar ---
        last = df.iloc[-1]
        prev = df.iloc[-2]
        if last["high"] < prev["high"] and last["low"] > prev["low"]:
            patterns.append({"pattern": "INSIDE_BAR", "significance": "NEUTRAL (breakout pending)"})

        bull = sum(1 for p in patterns if p["significance"] == "BULLISH")
        bear = sum(1 for p in patterns if p["significance"] == "BEARISH")
        # Compact: only pattern names and overall bias
        result = {
            "pair": pair,
            "patterns": [p["pattern"] for p in patterns],
            "bias": "BULL" if bull > bear else "BEAR" if bear > bull else "NEUTRAL",
        }
        return json.dumps(result)

    except Exception as e:
        logger.error(f"Error detecting patterns for {pair}: {e}")
        return json.dumps({"error": str(e), "pair": pair})


@tool("find_support_resistance")
def find_support_resistance(pair: str) -> str:
    """
    Find key support and resistance zones using price action analysis.
    Analyzes swing highs/lows across multiple timeframes (1h, 4h).
    Returns price levels ranked by number of touches (strength).
    """
    try:
        ex = _get_exchange()
        zones: List[Dict] = []

        for tf, weight in [("1h", 1), ("4h", 2)]:
            candles = ex.get_klines(pair, tf, 100)
            if len(candles) < 20:
                continue

            df = pd.DataFrame(candles)
            current_price = df["close"].iloc[-1]

            # Find swing points
            for i in range(2, len(df) - 2):
                # Swing high
                if df["high"].iloc[i] > max(df["high"].iloc[i-2:i].max(), df["high"].iloc[i+1:i+3].max()):
                    zones.append({
                        "type": "RESISTANCE",
                        "price": round(float(df["high"].iloc[i]), 2),
                        "weight": weight,
                    })
                # Swing low
                if df["low"].iloc[i] < min(df["low"].iloc[i-2:i].min(), df["low"].iloc[i+1:i+3].min()):
                    zones.append({
                        "type": "SUPPORT",
                        "price": round(float(df["low"].iloc[i]), 2),
                        "weight": weight,
                    })

        if not zones:
            return json.dumps({"pair": pair, "zones": [], "error": "Insufficient data"})

        # Cluster nearby zones (within 0.3% of each other)
        clustered = _cluster_zones(zones)

        # Sort by strength (total weight)
        clustered.sort(key=lambda z: z["strength"], reverse=True)

        current = float(ex.get_current_price(pair))

        supports = sorted([z for z in clustered if z["price"] < current], key=lambda z: z["strength"], reverse=True)[:3]
        resistances = sorted([z for z in clustered if z["price"] > current], key=lambda z: z["strength"], reverse=True)[:3]

        result = {
            "pair": pair,
            "price": current,
            "support": [z["price"] for z in supports],
            "resistance": [z["price"] for z in resistances],
        }
        return json.dumps(result)

    except Exception as e:
        logger.error(f"Error finding S/R for {pair}: {e}")
        return json.dumps({"error": str(e), "pair": pair})


def _cluster_zones(zones: List[Dict], tolerance_pct: float = 0.3) -> List[Dict]:
    """Cluster nearby price zones into single zones with combined strength."""
    if not zones:
        return []

    sorted_zones = sorted(zones, key=lambda z: z["price"])
    clustered = []
    current_cluster = [sorted_zones[0]]

    for zone in sorted_zones[1:]:
        cluster_avg = sum(z["price"] for z in current_cluster) / len(current_cluster)
        if abs(zone["price"] - cluster_avg) / cluster_avg * 100 < tolerance_pct:
            current_cluster.append(zone)
        else:
            clustered.append(_merge_cluster(current_cluster))
            current_cluster = [zone]

    if current_cluster:
        clustered.append(_merge_cluster(current_cluster))

    return clustered


def _merge_cluster(cluster: List[Dict]) -> Dict:
    """Merge a cluster of zones into a single zone."""
    avg_price = sum(z["price"] for z in cluster) / len(cluster)
    total_weight = sum(z["weight"] for z in cluster)
    zone_type = max(set(z["type"] for z in cluster), key=lambda t: sum(1 for z in cluster if z["type"] == t))

    return {
        "type": zone_type,
        "price": round(avg_price, 2),
        "strength": total_weight,
        "touches": len(cluster),
    }


@tool("analyze_volume_profile")
def analyze_volume_profile(pair: str) -> str:
    """
    Analyze volume distribution at different price levels.
    Identifies high-volume nodes (HVN) and low-volume nodes (LVN).
    HVNs act as support/resistance, LVNs are areas of fast price movement.
    """
    try:
        ex = _get_exchange()
        candles = ex.get_klines(pair, "1h", 100)

        if len(candles) < 20:
            return json.dumps({"pair": pair, "error": "Insufficient data"})

        df = pd.DataFrame(candles)

        # Create price bins
        price_min = df["low"].min()
        price_max = df["high"].max()
        num_bins = 20
        bins = np.linspace(price_min, price_max, num_bins + 1)

        # Distribute volume across price bins
        volume_profile = np.zeros(num_bins)
        for _, row in df.iterrows():
            candle_range = row["high"] - row["low"]
            if candle_range == 0:
                continue
            for j in range(num_bins):
                bin_low = bins[j]
                bin_high = bins[j + 1]
                # Overlap between candle and bin
                overlap = max(0, min(row["high"], bin_high) - max(row["low"], bin_low))
                volume_profile[j] += row["volume"] * (overlap / candle_range)

        # Find HVN and LVN
        avg_vol = np.mean(volume_profile)
        current_price = df["close"].iloc[-1]

        hvn = []
        lvn = []
        for j in range(num_bins):
            mid_price = (bins[j] + bins[j + 1]) / 2
            vol = volume_profile[j]
            if vol > avg_vol * 1.5:
                hvn.append({"price": round(float(mid_price), 2), "volume": round(float(vol), 2)})
            elif vol < avg_vol * 0.5:
                lvn.append({"price": round(float(mid_price), 2), "volume": round(float(vol), 2)})

        # Point of Control (POC) - highest volume price
        poc_idx = int(np.argmax(volume_profile))
        poc_price = (bins[poc_idx] + bins[poc_idx + 1]) / 2

        # Value Area (70% volume range)
        total_vol = np.sum(volume_profile)
        sorted_indices = np.argsort(volume_profile)[::-1]
        cumulative = 0
        va_indices = []
        for idx in sorted_indices:
            cumulative += volume_profile[idx]
            va_indices.append(idx)
            if cumulative >= total_vol * 0.7:
                break

        va_low = bins[min(va_indices)]
        va_high = bins[max(va_indices) + 1]

        result = {
            "pair": pair,
            "poc": round(float(poc_price), 2),
            "va_high": round(float(va_high), 2),
            "va_low": round(float(va_low), 2),
            "in_va": bool(va_low <= current_price <= va_high),
            "vs_poc": "ABOVE" if current_price > poc_price else "BELOW",
        }
        return json.dumps(result)

    except Exception as e:
        logger.error(f"Error analyzing volume profile for {pair}: {e}")
        return json.dumps({"error": str(e), "pair": pair})
