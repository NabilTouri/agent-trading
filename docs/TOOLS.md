# Tools Documentation

All tools use CrewAI's `@tool` decorator and return JSON strings. Each tool wraps existing exchange/data infrastructure.

## Market Data Tools (`tools/market_data.py`)

| Tool | Args | Description |
|------|------|-------------|
| `get_orderbook` | `pair` | Top 10 bids/asks, imbalance ratio, buy/sell pressure interpretation |
| `get_funding_rate` | `pair` | Current/historical funding rates, annualized rate, positioning interpretation |
| `get_klines` | `pair`, `interval`, `limit` | OHLCV candles with summary statistics (period high/low, range %) |
| `get_current_price` | `pair` | Latest price from Binance Futures |

## Technical Analysis Tools (`tools/technical_analysis.py`)

| Tool | Args | Description |
|------|------|-------------|
| `calculate_indicators` | `pair`, `timeframe` | RSI, MACD, BB, ATR, EMA20/50/200, Stochastic, ADX, volume ratio with interpretations |
| `detect_chart_patterns` | `pair` | Higher highs/lows, double top/bottom, engulfing candles, inside bars |
| `find_support_resistance` | `pair` | Multi-timeframe (1h/4h) S/R zones with clustering and strength scoring |
| `analyze_volume_profile` | `pair` | HVN/LVN, Point of Control, Value Area (70%), price vs POC |

## Sentiment Tools (`tools/sentiment_tools.py`)

| Tool | Args | Description |
|------|------|-------------|
| `get_fear_greed_index` | — | Crypto Fear & Greed (0-100), 7-day average, trend, contrarian signal |
| `get_crypto_news` | `pair` | Headlines from CoinDesk API with native SENTIMENT per article (no heuristic) |
| `get_social_sentiment` | `pair` | Reddit subscribers/active users, Twitter followers, momentum |
| `get_derivatives_positioning` | `pair` | Open interest, long/short ratio, squeeze risk from Binance |

## Risk Management Tools (`tools/risk_tools.py`)

| Tool | Args | Description |
|------|------|-------------|
| `get_portfolio_state` | — | Balance, positions, exposure, drawdown, win rate, P&L |
| `calculate_kelly_position_size` | `win_rate`, `avg_win`, `avg_loss`, `balance` | Full/half Kelly, capped to risk_per_trade |
| `calculate_var` | `pair`, `position_size`, `confidence` | 1-day VaR and CVaR via historical simulation |
| `check_portfolio_correlation` | `pair` | Correlation with existing positions (hourly returns) |
| `estimate_slippage` | `pair`, `order_size_usd` | Orderbook walk simulation, spread check |
| `analyze_market_depth` | `pair` | Bid/ask depth at 0.5%, 1%, 2% levels, liquidity assessment |
