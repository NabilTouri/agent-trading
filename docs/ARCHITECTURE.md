# AI Trading Bot - Architecture

## Overview

Multi-agent trading system using Claude AI for decision making.

## System Components

```
┌─────────────────────────────────────────────────────────────┐
│                     MULTI-AGENT SYSTEM                       │
├─────────────────┬─────────────────┬─────────────────────────┤
│ Market Analysis │   Sentiment     │   Risk Management       │
│   (Sonnet 4)    │   (Sonnet 4)    │     (Sonnet 4)          │
├─────────────────┴─────────────────┴─────────────────────────┤
│                    ORCHESTRATOR (Opus 4)                     │
│               Final Decision Making & Conflict Resolution    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      EXECUTION ENGINE                        │
├────────────────────────┬────────────────────────────────────┤
│    Strategy Loop       │       Execution Loop                │
│    (30min cycle)       │       (10sec cycle)                 │
└────────────────────────┴────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        ┌─────────┐     ┌─────────┐     ┌─────────┐
        │  Redis  │     │ Binance │     │Telegram │
        │   DB    │     │   API   │     │  Alerts │
        └─────────┘     └─────────┘     └─────────┘
```

## Data Flow

1. **Strategy Loop** (every 30 minutes):
   - Fetch market data (OHLCV, indicators)
   - Call Market Analysis Agent
   - Call Sentiment Agent
   - Call Risk Management Agent
   - Orchestrator makes final decision
   - Generate Signal

2. **Execution Loop** (every 10 seconds):
   - Check for new signals
   - Execute trades if criteria met
   - Monitor open positions
   - Trigger stop loss / take profit

## Agent Decision Process

```
Market Data → [Market Agent] → Technical Signal
News Data   → [Sentiment Agent] → Sentiment Score
Account Info → [Risk Agent] → Position Sizing

All Results → [Orchestrator] → FINAL DECISION (BUY/SELL/HOLD)
```

## Risk Management

- Max 2% risk per trade
- Max 3 concurrent positions
- Stop loss: Entry ± 2×ATR
- Take profit: 2:1 risk/reward minimum
- 20% max drawdown circuit breaker
