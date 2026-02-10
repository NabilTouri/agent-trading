#!/bin/bash
# =============================================================================
# stop.sh — Graceful Stop
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

if docker compose version &>/dev/null; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &>/dev/null; then
    COMPOSE_CMD="docker-compose"
else
    echo -e "${RED}Docker Compose not found!${NC}"
    exit 1
fi

CLEAN=false
if [[ "${1:-}" == "--clean" ]]; then
    CLEAN=true
fi

echo -e "${BOLD}"
echo "╔═══════════════════════════════════════════════╗"
echo "║       🛑 AI TRADING BOT — STOP               ║"
echo "╚═══════════════════════════════════════════════╝"
echo -e "${NC}"

# Show current status
log_info "Current status:"
$COMPOSE_CMD ps 2>/dev/null || true
echo ""

if [ "$CLEAN" = true ]; then
    log_warn "Clean mode: will remove volumes and networks too!"
    read -p "Are you sure? (y/N): " confirm
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        $COMPOSE_CMD down -v --remove-orphans
        log_success "All services stopped. Volumes and networks removed."
    else
        log_info "Cancelled."
        exit 0
    fi
else
    $COMPOSE_CMD down --remove-orphans
    log_success "All services stopped. Data volumes preserved."
fi

echo ""
echo "To restart: ./scripts/deploy.sh"
echo "Quick restart: ./scripts/update.sh --no-build"
echo ""
