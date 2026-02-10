#!/bin/bash
# =============================================================================
# restart.sh — Restart Services
# AI Trading Bot Multi-Agent
# Usage: ./restart.sh              (all services)
#        ./restart.sh bot          (only bot)
#        ./restart.sh bot api      (bot + api)
# =============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

log_info()    { echo -e "${BLUE}[INFO]${NC}  $1"; }
log_success() { echo -e "${GREEN}[✅]${NC}    $1"; }

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
echo "║       🔄 AI TRADING BOT — RESTART             ║"
echo "╚═══════════════════════════════════════════════╝"
echo -e "${NC}"

SERVICES=("$@")

if [ ${#SERVICES[@]} -eq 0 ]; then
    log_info "Restarting ALL services..."
    $COMPOSE_CMD restart
    log_success "All services restarted"
else
    for svc in "${SERVICES[@]}"; do
        log_info "Restarting $svc..."
        $COMPOSE_CMD restart "$svc"
        log_success "$svc restarted"
    done
fi

echo ""
sleep 2
log_info "Current status:"
$COMPOSE_CMD ps
echo ""
