"""
Sentiment analysis tools for CrewAI agents.

These tools gather qualitative market signals: news sentiment, social media,
Fear & Greed index, and derivatives positioning data.
"""

import json
from datetime import datetime
import aiohttp
import asyncio
from crewai.tools import tool
from loguru import logger


def _run_async(coro):
    """Run an async coroutine synchronously (for CrewAI tool compatibility)."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result(timeout=30)
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def _get_exchange():
    from core.exchange import exchange
    return exchange


@tool("get_fear_greed_index")
def get_fear_greed_index() -> str:
    """
    Fetch the current Crypto Fear & Greed Index (0-100).
    0-24 = Extreme Fear (potential buying opportunity).
    25-49 = Fear.
    50 = Neutral.
    51-74 = Greed.
    75-100 = Extreme Greed (potential sell signal).
    Use this to gauge overall market sentiment.
    """
    async def _fetch():
        try:
            url = "https://api.alternative.me/fng/?limit=7&format=json"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        entries = data.get("data", [])

                        if not entries:
                            return json.dumps({"error": "No data available"})

                        current = entries[0]
                        value = int(current["value"])
                        classification = current["value_classification"]

                        # Historical context
                        history = [
                            {"value": int(e["value"]), "classification": e["value_classification"]}
                            for e in entries[:7]
                        ]
                        avg_7d = sum(int(e["value"]) for e in entries[:7]) / min(len(entries), 7)

                        result = {
                            "current_value": value,
                            "classification": classification,
                            "7day_average": round(avg_7d, 1),
                            "trend": (
                                "IMPROVING" if value > avg_7d
                                else "DETERIORATING" if value < avg_7d
                                else "STABLE"
                            ),
                            "history_7d": history,
                            "signal": (
                                "CONTRARIAN_BUY" if value < 25
                                else "CONTRARIAN_SELL" if value > 75
                                else "NEUTRAL"
                            ),
                        }
                        return json.dumps(result, indent=2)
                    else:
                        return json.dumps({"error": f"API returned status {resp.status}"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    return _run_async(_fetch())


@tool("get_crypto_news")
def get_crypto_news(pair: str) -> str:
    """
    Fetch latest cryptocurrency news headlines with API-provided sentiment.
    Uses the CoinDesk data API which returns native SENTIMENT per article
    (POSITIVE, NEGATIVE, NEUTRAL) — no heuristic classification needed.
    Use this to identify major bullish or bearish catalysts.
    """
    async def _fetch():
        try:
            # Extract the base asset (e.g., BTC from BTC/USDT)
            symbol = pair.split("/")[0].upper()
            url = (
                f"https://data-api.coindesk.com/news/v1/article/list"
                f"?lang=EN&categories={symbol}&limit=10"
            )

            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        articles = data.get("Data", [])[:10]

                        if not articles:
                            return json.dumps({
                                "pair": pair,
                                "news_count": 0,
                                "articles": [],
                                "overall_sentiment": "NO_DATA",
                            })

                        # Map API sentiment to trading sentiment
                        _SENTIMENT_MAP = {
                            "POSITIVE": "BULLISH",
                            "NEGATIVE": "BEARISH",
                            "NEUTRAL": "NEUTRAL",
                        }

                        headlines = []
                        for article in articles:
                            api_sentiment = article.get("SENTIMENT", "NEUTRAL")
                            sentiment = _SENTIMENT_MAP.get(api_sentiment, "NEUTRAL")

                            # Extract source name
                            source_data = article.get("SOURCE_DATA", {})
                            source_name = source_data.get("NAME", article.get("AUTHORS", "unknown"))

                            # Extract categories
                            categories = [
                                c.get("NAME", "")
                                for c in article.get("CATEGORY_DATA", [])
                            ]

                            headlines.append({
                                "title": article.get("TITLE", "")[:150],
                                "source": source_name,
                                "sentiment": sentiment,
                                "api_sentiment": api_sentiment,
                                "published": article.get("PUBLISHED_ON", 0),
                                "categories": categories,
                                "url": article.get("URL", ""),
                            })

                        bullish = sum(1 for h in headlines if h["sentiment"] == "BULLISH")
                        bearish = sum(1 for h in headlines if h["sentiment"] == "BEARISH")
                        neutral = len(headlines) - bullish - bearish

                        result = {
                            "pair": pair,
                            "news_count": len(headlines),
                            "articles": headlines,
                            "bullish_count": bullish,
                            "bearish_count": bearish,
                            "neutral_count": neutral,
                            "overall_sentiment": (
                                "BULLISH" if bullish > bearish + 2
                                else "BEARISH" if bearish > bullish + 2
                                else "MIXED"
                            ),
                            "sentiment_source": "CoinDesk API (native)",
                        }
                        return json.dumps(result, indent=2)
                    else:
                        return json.dumps({"error": f"API returned status {resp.status}"})
        except Exception as e:
            return json.dumps({"error": str(e), "pair": pair})

    return _run_async(_fetch())


# _classify_headline removed — CoinDesk API provides native SENTIMENT per article


@tool("get_social_sentiment")
def get_social_sentiment(pair: str) -> str:
    """
    Analyze social media sentiment for a trading pair.
    Uses CryptoCompare social stats as a proxy for social momentum.
    Higher social activity during price moves confirms the trend.
    """
    async def _fetch():
        try:
            symbol = pair.split("/")[0]
            url = f"https://min-api.cryptocompare.com/data/social/coin/latest?coinId=1182"

            # Map common symbols to CryptoCompare coin IDs
            coin_ids = {"BTC": "1182", "ETH": "7605", "SOL": "934443", "BNB": "204788"}
            coin_id = coin_ids.get(symbol, "1182")
            url = f"https://min-api.cryptocompare.com/data/social/coin/latest?coinId={coin_id}"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        social = data.get("Data", {})

                        reddit = social.get("Reddit", {})
                        twitter = social.get("Twitter", {})

                        result = {
                            "pair": pair,
                            "reddit": {
                                "subscribers": reddit.get("subscribers", 0),
                                "active_users": reddit.get("active_users", 0),
                                "posts_per_day": reddit.get("posts_per_day", 0),
                            },
                            "twitter": {
                                "followers": twitter.get("followers", 0),
                            },
                            "social_momentum": (
                                "HIGH" if reddit.get("active_users", 0) > 5000
                                else "MODERATE" if reddit.get("active_users", 0) > 1000
                                else "LOW"
                            ),
                        }
                        return json.dumps(result, indent=2)
                    else:
                        return json.dumps({"error": f"API returned status {resp.status}"})
        except Exception as e:
            return json.dumps({"error": str(e), "pair": pair})

    return _run_async(_fetch())


@tool("get_derivatives_positioning")
def get_derivatives_positioning(pair: str) -> str:
    """
    Fetch derivatives market positioning data for a trading pair.
    Returns open interest, long/short ratio, and recent liquidations.
    High OI + extreme L/S ratio = potential for squeeze.
    """
    try:
        ex = _get_exchange()
        symbol = pair.replace("/", "")

        # Open Interest
        try:
            oi_data = ex.client.futures_open_interest(symbol=symbol)
            open_interest = float(oi_data.get("openInterest", 0))
        except Exception:
            open_interest = 0

        # Long/Short Ratio (top traders)
        try:
            ls_data = ex.client.futures_top_longshort_account_ratio(
                symbol=symbol, period="1h", limit=1
            )
            if ls_data:
                long_ratio = float(ls_data[0].get("longAccount", 0.5))
                short_ratio = float(ls_data[0].get("shortAccount", 0.5))
                ls_ratio = long_ratio / short_ratio if short_ratio > 0 else 1.0
            else:
                long_ratio = short_ratio = 0.5
                ls_ratio = 1.0
        except Exception:
            long_ratio = short_ratio = 0.5
            ls_ratio = 1.0

        result = {
            "pair": pair,
            "open_interest": open_interest,
            "long_short_ratio": {
                "long_pct": round(long_ratio * 100, 1),
                "short_pct": round(short_ratio * 100, 1),
                "ratio": round(ls_ratio, 3),
            },
            "positioning_signal": (
                "CROWDED_LONGS" if ls_ratio > 1.5
                else "CROWDED_SHORTS" if ls_ratio < 0.67
                else "BALANCED"
            ),
            "squeeze_risk": (
                "HIGH (long squeeze)" if ls_ratio > 2.0
                else "HIGH (short squeeze)" if ls_ratio < 0.5
                else "MODERATE" if ls_ratio > 1.5 or ls_ratio < 0.67
                else "LOW"
            ),
        }
        return json.dumps(result, indent=2)

    except Exception as e:
        logger.error(f"Error fetching derivatives data for {pair}: {e}")
        return json.dumps({"error": str(e), "pair": pair})
