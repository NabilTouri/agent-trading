"""
Market data tools for CrewAI agents.

These tools provide real-time market data from Binance: orderbook,
funding rates, candlestick data, and current prices.
"""

import json
from typing import Optional
from crewai.tools import tool
from loguru import logger


def _get_exchange():
    """Lazy import to avoid circular dependency."""
    from core.exchange import exchange
    return exchange


def _get_db():
    """Lazy import to avoid circular dependency."""
    from core.database import db
    return db


@tool("get_orderbook")
def get_orderbook(pair: str) -> str:
    """
    Fetch the live orderbook for a trading pair.
    Returns top 20 bids and asks with calculated imbalance ratio.
    Use this to gauge buy/sell pressure and liquidity around current price.
    """
    try:
        ex = _get_exchange()
        symbol = pair.replace("/", "")

        orderbook = ex.client.futures_order_book(symbol=symbol, limit=20)

        bids = [{"price": float(b[0]), "qty": float(b[1])} for b in orderbook["bids"][:10]]
        asks = [{"price": float(a[0]), "qty": float(a[1])} for a in orderbook["asks"][:10]]

        bid_volume = sum(b["qty"] for b in bids)
        ask_volume = sum(a["qty"] for a in asks)
        total = bid_volume + ask_volume
        imbalance = ((bid_volume - ask_volume) / total * 100) if total > 0 else 0

        result = {
            "pair": pair,
            "best_bid": bids[0]["price"] if bids else 0,
            "best_ask": asks[0]["price"] if asks else 0,
            "bid_vol": round(bid_volume, 2),
            "ask_vol": round(ask_volume, 2),
            "imbalance_pct": round(imbalance, 2),
            "signal": (
                "BUY_PRESSURE" if imbalance > 20
                else "SELL_PRESSURE" if imbalance < -20
                else "BALANCED"
            ),
        }
        return json.dumps(result)

    except Exception as e:
        logger.error(f"Error fetching orderbook for {pair}: {e}")
        return json.dumps({"error": str(e), "pair": pair})


@tool("get_funding_rate")
def get_funding_rate(pair: str) -> str:
    """
    Fetch the current funding rate for a futures trading pair.
    Positive funding = longs pay shorts (bullish crowding).
    Negative funding = shorts pay longs (bearish crowding).
    High absolute values suggest over-leveraged positioning.
    """
    try:
        ex = _get_exchange()
        symbol = pair.replace("/", "")

        funding = ex.client.futures_funding_rate(symbol=symbol, limit=3)

        if not funding:
            return json.dumps({"pair": pair, "error": "No funding data"})

        current = float(funding[-1]["fundingRate"])
        previous = [float(f["fundingRate"]) for f in funding[:-1]]
        avg_recent = sum(previous) / len(previous) if previous else current

        result = {
            "pair": pair,
            "rate_pct": round(current * 100, 4),
            "annualized_pct": round(current * 100 * 3 * 365, 2),
            "signal": (
                "CROWDED_LONGS" if current > 0.001
                else "BULLISH" if current > 0.0001
                else "CROWDED_SHORTS" if current < -0.001
                else "BEARISH" if current < -0.0001
                else "NEUTRAL"
            ),
        }
        return json.dumps(result)

    except Exception as e:
        logger.error(f"Error fetching funding rate for {pair}: {e}")
        return json.dumps({"error": str(e), "pair": pair})


@tool("get_klines")
def get_klines(pair: str, interval: str = "1h", limit: int = 50) -> str:
    """
    Fetch OHLCV candlestick data for a trading pair.
    Returns open, high, low, close, volume for each candle.
    Supported intervals: 1m, 5m, 15m, 1h, 4h, 1d.
    Use this for price action analysis and trend identification.
    """
    try:
        ex = _get_exchange()
        candles = ex.get_klines(pair, interval, min(limit, 100))

        if not candles:
            return json.dumps({"pair": pair, "interval": interval, "candles": []})

        # Summary stats only — no individual candles to save tokens
        all_closes = [c["close"] for c in candles]
        all_highs = [c["high"] for c in candles]
        all_lows = [c["low"] for c in candles]
        all_vols = [c["volume"] for c in candles]

        # Last 3 closes for recent direction
        last3 = all_closes[-3:]

        result = {
            "pair": pair,
            "interval": interval,
            "candles": len(candles),
            "current": round(all_closes[-1], 2),
            "high": round(max(all_highs), 2),
            "low": round(min(all_lows), 2),
            "last3_closes": [round(c, 2) for c in last3],
            "avg_vol": round(sum(all_vols) / len(all_vols), 2),
            "range_pct": round(
                ((max(all_highs) - min(all_lows)) / min(all_lows)) * 100, 2
            ) if min(all_lows) > 0 else 0,
        }
        return json.dumps(result)

    except Exception as e:
        logger.error(f"Error fetching klines for {pair}: {e}")
        return json.dumps({"error": str(e), "pair": pair})


@tool("get_current_price")
def get_current_price(pair: str) -> str:
    """
    Get the current market price for a trading pair.
    Returns the latest price from Binance Futures.
    """
    try:
        ex = _get_exchange()
        price = ex.get_current_price(pair)

        return json.dumps({
            "pair": pair,
            "price": price,
        })

    except Exception as e:
        logger.error(f"Error fetching price for {pair}: {e}")
        return json.dumps({"error": str(e), "pair": pair})
