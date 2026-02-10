#!/bin/bash
# =============================================================================
# emergency-stop.sh — Emergency Stop (Close Positions + Shutdown)
# AI Trading Bot Multi-Agent
# =============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

echo -e "${RED}${BOLD}"
echo "╔═══════════════════════════════════════════════╗"
echo "║     🚨 EMERGENCY STOP — AI TRADING BOT        ║"
echo "╚═══════════════════════════════════════════════╝"
echo -e "${NC}"
echo -e "${RED}This will:${NC}"
echo "  1. Close ALL open positions via API"
echo "  2. Stop ALL trading containers"
echo ""

# Skip confirmation with --force flag
if [[ "${1:-}" != "--force" ]]; then
    read -p "⚠️  Continue with emergency stop? (y/N): " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        log_info "Cancelled."
        exit 0
    fi
fi

echo ""

# ==== Step 1: Close Positions via API ====
log_info "Step 1: Closing all open positions..."

API_RESPONSE=$(curl -sf -X POST http://localhost:8000/api/control/emergency-stop 2>/dev/null) && {
    log_success "Emergency stop API called successfully"
    echo "  Response: $API_RESPONSE"
    # Give a moment for positions to close
    log_info "Waiting 5 seconds for positions to close..."
    sleep 5
} || {
    log_warn "API not responding — positions may not have been closed"
    log_warn "If the bot was trading, manually check Binance for open positions!"
}

echo ""

# ==== Step 2: Stop Containers ====
log_info "Step 2: Stopping all containers..."
$COMPOSE_CMD down --remove-orphans
log_success "All containers stopped"

echo ""

# ==== Summary ====
echo -e "${RED}${BOLD}━━━ EMERGENCY STOP COMPLETE ━━━${NC}"
echo ""
echo "📋 Checklist:"
echo "  ✅ Emergency stop API called"
echo "  ✅ All containers stopped"
echo ""
echo -e "${YELLOW}⚠️  IMPORTANT: Verify on Binance that all positions are closed!${NC}"
TESTNET_MODE=$(grep "^BINANCE_TESTNET=" .env 2>/dev/null | cut -d'=' -f2 | tr -d ' ' || echo "true")
if [ "$TESTNET_MODE" = "true" ]; then
    echo "  🔗 https://testnet.binancefuture.com"
else
    echo "  🔗 https://www.binance.com/en/futures"
fi
echo ""
echo "To restart: ./scripts/deploy.sh"
echo ""
