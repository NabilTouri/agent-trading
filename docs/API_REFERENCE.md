# API Reference

## Base URL

```
http://localhost:8000
```

## Endpoints

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |

### System

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/system/metrics` | Overall system metrics |
| GET | `/api/system/balance` | Exchange balance |
| GET | `/api/system/prices` | Current prices |
| GET | `/api/system/status` | Service status |

### Trades

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/trades/` | Trade history |
| GET | `/api/trades/stats` | Performance stats |
| GET | `/api/trades/recent` | Recent trades |

### Positions

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/positions/current` | Open positions |
| GET | `/api/positions/count` | Position count |

### Signals

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/signals/history` | Signal history |
| GET | `/api/signals/latest` | Latest signal |
| GET | `/api/signals/latest/all` | Latest for all pairs |

### Control

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/control/emergency-stop` | Close all positions |
| POST | `/api/control/reset-capital` | Reset capital |

## Example Responses

### GET /api/system/metrics

```json
{
  "capital": {
    "current": 3150.00,
    "initial": 3000.00,
    "pnl": 150.00,
    "pnl_percent": 5.00
  },
  "performance": {
    "total_trades": 25,
    "win_rate": 52.00,
    "profit_factor": 1.35,
    "total_pnl": 150.00
  },
  "positions": {
    "open": 1,
    "max": 3
  }
}
```

### GET /api/positions/current

```json
[
  {
    "position_id": "abc-123",
    "pair": "BTC/USDT",
    "side": "LONG",
    "entry_price": 50000.00,
    "current_price": 51000.00,
    "size": 60.00,
    "unrealized_pnl": 1.20,
    "unrealized_pnl_percent": 2.00
  }
]
```
