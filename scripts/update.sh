#!/bin/bash
# =============================================================================
# update.sh — Quick Update (Git Pull → Build → Restart) — No Tests
# AI Trading Bot Multi-Agent
# =============================================================================
set -euo pipefail

# Colors
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
log_error()   { echo -e "${RED}[❌]${NC}    $1"; }
log_step()    { echo -e "\n${CYAN}${BOLD}━━━ $1 ━━━${NC}"; }

# Detect compose command
if docker compose version &>/dev/null; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &>/dev/null; then
    COMPOSE_CMD="docker-compose"
else
    log_error "Docker Compose not found!"
    exit 1
fi

echo -e "${BOLD}"
echo "╔═══════════════════════════════════════════════╗"
echo "║       🔄 AI TRADING BOT — QUICK UPDATE       ║"
echo "╚═══════════════════════════════════════════════╝"
echo -e "${NC}"
echo "📅 $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Parse flags
SKIP_BUILD=false
SERVICE=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --no-build) SKIP_BUILD=true; shift ;;
        --service)  SERVICE="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: ./update.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --no-build       Skip Docker build (only pull + restart)"
            echo "  --service NAME   Update only a specific service (bot, api, dashboard)"
            echo "  -h, --help       Show this help"
            exit 0
            ;;
        *) SERVICE="$1"; shift ;;
    esac
done

# ==== Git Pull ====
log_step "Pulling Latest Code"

if [ -d ".git" ] && command -v git &>/dev/null; then
    BEFORE=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
    if git pull 2>&1 | tail -5; then
        AFTER=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
        if [ "$BEFORE" = "$AFTER" ]; then
            log_info "Already up to date"
        else
            log_success "Updated: ${BEFORE:0:7} → ${AFTER:0:7}"
        fi
    else
        log_error "Git pull failed"
        exit 1
    fi
else
    log_info "Git not available — skipping pull"
fi

# ==== Build ====
if [ "$SKIP_BUILD" = false ]; then
    log_step "Rebuilding Images"
    if [ -n "$SERVICE" ]; then
        log_info "Building $SERVICE..."
        $COMPOSE_CMD build "$SERVICE"
    else
        log_info "Building all services..."
        $COMPOSE_CMD build --parallel
    fi
    log_success "Build completed"
else
    log_info "Skipping build (--no-build)"
fi

# ==== Restart ====
log_step "Restarting Services"

if [ -n "$SERVICE" ]; then
    log_info "Restarting $SERVICE..."
    $COMPOSE_CMD up -d --no-deps "$SERVICE"
    log_success "$SERVICE restarted"
else
    log_info "Restarting all services..."
    $COMPOSE_CMD up -d
    log_success "All services restarted"
fi

# ==== Status ====
sleep 3
log_step "Current Status"
$COMPOSE_CMD ps
echo ""
echo -e "${GREEN}${BOLD}✅ Update complete!${NC}"
echo ""
