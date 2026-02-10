#!/bin/bash
# =============================================================================
# status.sh — Health Check & Status Overview
# AI Trading Bot Multi-Agent
# =============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

log_info()    { echo -e "${BLUE}[INFO]${NC}  $1"; }
log_success() { echo -e "${GREEN}[✅]${NC}    $1"; }
log_warn()    { echo -e "${YELLOW}[⚠️]${NC}    $1"; }
log_error()   { echo -e "${RED}[❌]${NC}    $1"; }

if docker compose version &>/dev/null; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &>/dev/null; then
    COMPOSE_CMD="docker-compose"
else
    echo -e "${RED}Docker Compose not found!${NC}"
    exit 1
fi

echo -e "${BOLD}"
echo "╔═══════════════════════════════════════════════╗"
echo "║       📊 AI TRADING BOT — STATUS              ║"
echo "╚═══════════════════════════════════════════════╝"
echo -e "${NC}"
echo "📅 $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# ==== Container Status ====
echo -e "${CYAN}${BOLD}━━━ Container Status ━━━${NC}"
$COMPOSE_CMD ps 2>/dev/null || echo "  No containers running"
echo ""

# ==== Health Checks ====
echo -e "${CYAN}${BOLD}━━━ Health Checks ━━━${NC}"

# Redis
if docker exec trading-redis redis-cli ping 2>/dev/null | grep -q "PONG"; then
    log_success "Redis: responding (PONG)"
else
    log_error "Redis: not responding"
fi

# API
API_HEALTH=$(curl -sf http://localhost:8000/health 2>/dev/null) && {
    log_success "API: healthy — $API_HEALTH"
} || {
    log_error "API: not responding (http://localhost:8000)"
}

# Dashboard
if curl -sf http://localhost:3000 >/dev/null 2>&1; then
    log_success "Dashboard: online (http://localhost:3000)"
else
    log_error "Dashboard: not responding (http://localhost:3000)"
fi

echo ""

# ==== Resource Usage ====
echo -e "${CYAN}${BOLD}━━━ Resource Usage ━━━${NC}"
CONTAINERS=$(docker ps --filter "name=trading-" --format "{{.Names}}" 2>/dev/null)
if [ -n "$CONTAINERS" ]; then
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.PIDs}}" $CONTAINERS 2>/dev/null
else
    echo "  No trading containers running"
fi
echo ""

# ==== Trading Mode ====
echo -e "${CYAN}${BOLD}━━━ Configuration ━━━${NC}"
TESTNET_MODE=$(grep "^BINANCE_TESTNET=" .env 2>/dev/null | cut -d'=' -f2 | tr -d ' ' || echo "unknown")
PAIRS=$(grep "^TRADING_PAIRS=" .env 2>/dev/null | cut -d'=' -f2 | tr -d ' ' || echo "unknown")
CAPITAL=$(grep "^INITIAL_CAPITAL=" .env 2>/dev/null | cut -d'=' -f2 | tr -d ' ' || echo "unknown")

if [ "$TESTNET_MODE" = "false" ]; then
    log_warn "Mode: ⚠️  MAINNET (real money!)"
else
    log_info "Mode: TESTNET"
fi
log_info "Pairs: $PAIRS"
log_info "Capital: \$$CAPITAL"
echo ""

# ==== Recent Logs (last 5 lines per service) ====
echo -e "${CYAN}${BOLD}━━━ Recent Bot Logs (last 5) ━━━${NC}"
$COMPOSE_CMD logs --tail 5 bot 2>/dev/null || echo "  No bot logs available"
echo ""
