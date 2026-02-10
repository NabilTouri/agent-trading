# AI Trading Bot Multi-Agent

Crypto trading bot basato su architettura **multi-agent con Claude AI**.

## 🚀 Quick Start

### 1. Clone & Setup

```bash
cd c:\Projects\agent-trading

# Copy environment template
cp .env.example .env

# Edit with your API keys
notepad .env
```

### 2. Configure API Keys

Edit `.env` with:

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-xxxxx  # From console.anthropic.com
BINANCE_API_KEY=xxxxx           # From testnet.binancefuture.com
BINANCE_SECRET_KEY=xxxxx

# Optional (for notifications)
TELEGRAM_BOT_TOKEN=xxxxx
TELEGRAM_CHAT_ID=xxxxx
```

### 3. Get Binance Testnet Keys

1. Go to https://testnet.binancefuture.com
2. Login with Gmail/GitHub
3. Generate API Key + Secret
4. Add to `.env`

### 4. Deploy with Docker

```bash
# Build and start all services
docker-compose up --build -d

# Verify setup
docker-compose run --rm bot python scripts/setup_testnet.py

# Check logs
docker-compose logs -f bot
```

### 5. Access Dashboard

Open http://localhost:3000

---

## 📁 Project Structure

```
ai-trading-bot/
├── agents/         # Multi-agent system (Claude AI)
├── core/           # Business logic (config, database, exchange)
├── services/       # External services (Telegram, backup)
├── bot/            # Trading loops (strategy, execution)
├── api/            # FastAPI backend
├── dashboard/      # Next.js frontend
├── scripts/        # Utility scripts
└── tests/          # Test suite
```

---

## 🤖 Multi-Agent Architecture (Phase 1)

| Agent | Model | Role |
|-------|-------|------|
| **Orchestrator** | Claude Haiku 3.5 | Final decision maker |
| **Market Analysis** | Claude Sonnet 4 | Technical analysis |
| **Risk Management** | Claude Sonnet 4 | Position sizing & stops |

> **Note**: Sentiment Agent will be added in Phase 2 (Month 3)

### Phase 2 Upgrade (Month 3)
- Add Sentiment Agent (Sonnet 4)
- Add News Feed service
- Upgrade Orchestrator Haiku → Sonnet 4
- Cost: $45 → $71/month

---

## 🔧 Configuration

Key settings in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `BINANCE_TESTNET` | `true` | Use testnet (set `false` for mainnet) |
| `INITIAL_CAPITAL` | `3000.0` | Starting capital in USDT |
| `RISK_PER_TRADE` | `0.02` | 2% risk per trade |
| `MAX_POSITIONS` | `3` | Maximum concurrent positions |
| `TRADING_PAIRS` | `BTC/USDT,ETH/USDT` | Pairs to trade |

---

## 💰 Cost Estimation (Phase 1)

| Item | Monthly Cost |
|------|-------------|
| Claude API | ~$45 |
| VPS (4GB) | ~$20-40 |
| **Total** | **~$65-85** |

---

## 📊 API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check |
| `GET /api/system/metrics` | System metrics |
| `GET /api/positions/current` | Open positions |
| `GET /api/trades/stats` | Performance stats |
| `GET /api/signals/history` | Signal history |
| `POST /api/control/emergency-stop` | Close all positions |

---

## 🧪 Testing

```bash
# Run tests
docker-compose run --rm bot pytest tests/ -v

# Verify connections
docker-compose run --rm bot python scripts/setup_testnet.py
```

---

## 🚀 Server Deployment Scripts

Shell scripts per gestire il bot direttamente sul server (VPS Linux). Tutti in `scripts/`.

> **Primo deploy**: rendi eseguibili con `chmod +x scripts/*.sh`

### Scenari principali

| Comando | Quando usarlo |
|---------|---------------|
| `./scripts/deploy.sh` | **Primo deploy** o deploy completo da zero |
| `./scripts/update.sh` | **Dopo un push** alla repo (quick update, no test) |
| `./scripts/stop.sh` | Fermare tutto in modo graceful |
| `./scripts/emergency-stop.sh` | **Emergenza** — chiude posizioni + spegne tutto |

### Operazioni quotidiane

```bash
# Status e health check di tutti i servizi
./scripts/status.sh

# Vedere i log del bot (follow in tempo reale)
./scripts/logs.sh -f bot

# Restart solo del bot dopo una modifica di config
./scripts/restart.sh bot

# Backup manuale Redis + Logs
./scripts/backup.sh
```

### Update rapido (dopo git push)

```bash
# Update completo: pull → build → restart
./scripts/update.sh

# Update solo un servizio
./scripts/update.sh --service bot

# Solo restart, senza rebuild
./scripts/update.sh --no-build
```

### Stop & Cleanup

```bash
# Stop graceful (mantiene dati)
./scripts/stop.sh

# Stop + rimuovi volumi e network
./scripts/stop.sh --clean
```

---

## ⚠️ Production Checklist

Before going live:

- [ ] Paper trade for 60+ days on testnet
- [ ] Achieve Sharpe ratio > 1.5
- [ ] Win rate > 45%
- [ ] Set `BINANCE_TESTNET=false`
- [ ] Configure Telegram alerts
- [ ] Setup monitoring

---

## 🛑 Emergency Stop

```bash
# Stop all trading immediately
curl -X POST http://localhost:8000/api/control/emergency-stop
```

---

**⚠️ DISCLAIMER**: Trading involves substantial risk. This bot is for educational purposes. Never risk more than you can afford to lose.
