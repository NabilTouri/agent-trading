# Agents Documentation

## Architecture Overview

The trading bot uses a **3-agent sequential pipeline** powered by [CrewAI](https://crewai.com/) with Claude Sonnet 4.

```
Market Analysis Agent → Sentiment Agent → Trading Operations Agent → TradeDecision
```

Each agent receives the output of the previous agent via CrewAI's sequential process. The final output is a structured `TradeDecision` (APPROVED or REJECTED).

---

## Agent 1: Market Analysis Agent

| Property | Value |
|----------|-------|
| **Role** | Senior Quantitative Market Analyst |
| **Model** | Claude Sonnet 4 |
| **Max Iterations** | 10 |
| **File** | `agents/market_analysis_agent.py` |

### Goal
Produce a complete quantitative market analysis including trend direction, multi-timeframe indicators, S/R zones, volume profile, orderbook sentiment, and a directional bias (LONG/SHORT/NEUTRAL) with confidence level.

### Tools (8)
| Tool | Module | Description |
|------|--------|-------------|
| `get_orderbook` | `tools/market_data.py` | Orderbook bids/asks with imbalance ratio |
| `get_funding_rate` | `tools/market_data.py` | Current funding rate with interpretation |
| `get_klines` | `tools/market_data.py` | OHLCV candlestick data |
| `get_current_price` | `tools/market_data.py` | Latest market price |
| `calculate_indicators` | `tools/technical_analysis.py` | RSI, MACD, BB, ATR, EMAs, Stochastic, ADX |
| `detect_chart_patterns` | `tools/technical_analysis.py` | Double tops/bottoms, engulfing, inside bars |
| `find_support_resistance` | `tools/technical_analysis.py` | Multi-timeframe S/R zones with clustering |
| `analyze_volume_profile` | `tools/technical_analysis.py` | HVN, LVN, POC, Value Area |

---

## Agent 2: Sentiment Agent

| Property | Value |
|----------|-------|
| **Role** | Market Sentiment Specialist |
| **Model** | Claude Sonnet 4 |
| **Max Iterations** | 8 |
| **File** | `agents/sentiment_agent.py` |

### Goal
Capture directional sentiment and institutional positioning. Determine whether sentiment aligns with or diverges from the technical analysis.

### Tools (4)
| Tool | Module | Description |
|------|--------|-------------|
| `get_fear_greed_index` | `tools/sentiment_tools.py` | Crypto Fear & Greed (0-100) with 7-day trend |
| `get_crypto_news` | `tools/sentiment_tools.py` | News headlines with sentiment classification |
| `get_social_sentiment` | `tools/sentiment_tools.py` | Reddit/Twitter activity and momentum |
| `get_derivatives_positioning` | `tools/sentiment_tools.py` | Open interest, L/S ratio, squeeze risk |

---

## Agent 3: Trading Operations Agent

| Property | Value |
|----------|-------|
| **Role** | Risk & Execution Manager |
| **Model** | Claude Sonnet 4 |
| **Max Iterations** | 10 |
| **File** | `agents/trading_ops_agent.py` |

### Goal
Validate risk, calculate position sizing, and produce a final APPROVED/REJECTED `TradeDecision` with full execution plan.

### Tools (6)
| Tool | Module | Description |
|------|--------|-------------|
| `get_portfolio_state` | `tools/risk_tools.py` | Balance, positions, exposure, drawdown, metrics |
| `calculate_kelly_position_size` | `tools/risk_tools.py` | Kelly Criterion with half-Kelly recommendation |
| `calculate_var` | `tools/risk_tools.py` | Value at Risk (historical simulation) + CVaR |
| `check_portfolio_correlation` | `tools/risk_tools.py` | Correlation with existing positions |
| `estimate_slippage` | `tools/risk_tools.py` | Orderbook walk slippage estimation |
| `analyze_market_depth` | `tools/risk_tools.py` | Liquidity at multiple price levels |

---

## Crew Assembly

The crew is assembled in `agents/crew.py` via the `TradingCrew` class:

```python
from agents.crew import TradingCrew

crew = TradingCrew("BTC/USDT")
decision = crew.run()

if decision and decision.decision == "APPROVED":
    # Execute trade
```

### Memory
Uses CrewAI's native `Memory` system with tuned scoring:
- Recency weight: 0.3
- Semantic weight: 0.5
- Importance weight: 0.2
- Half-life: 7 days

### Output Schema
The final output is a `TradeDecision` Pydantic model (defined in `core/models.py`):

```json
{
  "decision": "APPROVED",
  "pair": "BTC/USDT",
  "direction": "LONG",
  "confidence": 78,
  "position_size_usd": 200.0,
  "position_size_pct": 2.0,
  "entry": {"method": "LIMIT", "price": 50000.0, "orders": [...]},
  "stop_loss": {"price": 48500.0, "pct": 3.0, "type": "STOP_LIMIT"},
  "take_profit": [
    {"level": 1, "price": 52000.0, "size_pct": 50},
    {"level": 2, "price": 54000.0, "size_pct": 50}
  ],
  "risk_reward_ratio": 2.67,
  "reasoning": "..."
}
```
