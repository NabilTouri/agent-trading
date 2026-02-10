#!/bin/bash
# =============================================================================
# deploy.sh — Full Deploy (Setup → Test → Build → Launch)
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

# Project root (directory of this script, one level up)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# Logging
log_info()    { echo -e "${BLUE}[INFO]${NC}  $1"; }
log_success() { echo -e "${GREEN}[✅]${NC}    $1"; }
log_warn()    { echo -e "${YELLOW}[⚠️]${NC}    $1"; }
log_error()   { echo -e "${RED}[❌]${NC}    $1"; }
log_step()    { echo -e "\n${CYAN}${BOLD}━━━ $1 ━━━${NC}"; }

ERRORS=0

# ==== BANNER ====
echo -e "${BOLD}"
echo "╔═══════════════════════════════════════════════╗"
echo "║       🤖 AI TRADING BOT — FULL DEPLOY        ║"
echo "╚═══════════════════════════════════════════════╝"
echo -e "${NC}"
echo "📅 $(date '+%Y-%m-%d %H:%M:%S')"
echo "📁 Project: $PROJECT_DIR"
echo ""

# ==== STEP 1: Prerequisites ====
log_step "STEP 1/8: Checking Prerequisites"

# Docker
if command -v docker &>/dev/null; then
    DOCKER_VERSION=$(docker --version | awk '{print $3}' | tr -d ',')
    log_success "Docker installed (v$DOCKER_VERSION)"
else
    log_error "Docker not found. Install: https://docs.docker.com/engine/install/"
    exit 1
fi

# Docker Compose (v2 or v1)
if docker compose version &>/dev/null; then
    COMPOSE_CMD="docker compose"
    COMPOSE_VERSION=$(docker compose version --short 2>/dev/null || echo "v2")
    log_success "Docker Compose v2 ($COMPOSE_VERSION)"
elif command -v docker-compose &>/dev/null; then
    COMPOSE_CMD="docker-compose"
    COMPOSE_VERSION=$(docker-compose --version | awk '{print $4}' | tr -d ',')
    log_success "Docker Compose v1 ($COMPOSE_VERSION)"
else
    log_error "Docker Compose not found. Install: https://docs.docker.com/compose/install/"
    exit 1
fi

# Docker daemon running
if ! docker info &>/dev/null; then
    log_error "Docker daemon is not running. Start Docker first."
    exit 1
fi
log_success "Docker daemon is running"

# Git (optional, for pull)
if command -v git &>/dev/null; then
    log_success "Git installed"
    HAS_GIT=true
else
    log_warn "Git not found — skipping git pull"
    HAS_GIT=false
fi

# ==== STEP 2: Environment File ====
log_step "STEP 2/8: Checking Environment"

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        log_warn ".env not found — copied from .env.example"
        log_warn "⚡ EDIT .env WITH YOUR API KEYS BEFORE CONTINUING!"
        echo ""
        read -p "Press Enter after editing .env, or Ctrl+C to abort..."
    else
        log_error ".env and .env.example not found!"
        exit 1
    fi
else
    log_success ".env file exists"
fi

# ==== STEP 3: Validate .env ====
log_step "STEP 3/8: Validating Configuration"

validate_env_var() {
    local var_name="$1"
    local required="$2"
    local value
    value=$(grep "^${var_name}=" .env 2>/dev/null | cut -d'=' -f2- | tr -d ' "'"'"'')

    if [ -z "$value" ] || [ "$value" = "xxxxx" ] || [ "$value" = "sk-ant-xxxxx" ]; then
        if [ "$required" = "true" ]; then
            log_error "$var_name is not configured (REQUIRED)"
            ERRORS=$((ERRORS + 1))
        else
            log_warn "$var_name is not configured (optional)"
        fi
    else
        # Mask the value for security
        local masked="${value:0:8}..."
        log_success "$var_name configured ($masked)"
    fi
}

validate_env_var "ANTHROPIC_API_KEY" "true"
validate_env_var "BINANCE_API_KEY" "true"
validate_env_var "BINANCE_SECRET_KEY" "true"
validate_env_var "TELEGRAM_BOT_TOKEN" "false"
validate_env_var "TELEGRAM_CHAT_ID" "false"

if [ "$ERRORS" -gt 0 ]; then
    log_error "$ERRORS required variables are missing. Edit .env and re-run."
    exit 1
fi

# Check testnet mode
TESTNET_MODE=$(grep "^BINANCE_TESTNET=" .env 2>/dev/null | cut -d'=' -f2 | tr -d ' ')
if [ "$TESTNET_MODE" = "false" ]; then
    echo ""
    log_warn "⚠️  MAINNET MODE DETECTED! Real money is at risk!"
    read -p "Are you sure you want to deploy in MAINNET mode? (type YES): " confirm
    if [ "$confirm" != "YES" ]; then
        log_info "Deploy cancelled."
        exit 0
    fi
else
    log_success "Testnet mode enabled"
fi

# ==== STEP 4: Git Pull ====
log_step "STEP 4/8: Updating Code"

if [ "$HAS_GIT" = true ] && [ -d ".git" ]; then
    log_info "Pulling latest changes..."
    if git pull 2>&1 | tail -5; then
        log_success "Code updated"
    else
        log_warn "Git pull failed — continuing with current code"
    fi
else
    log_info "Skipping git pull (not a git repo or git not available)"
fi

# ==== STEP 5: Build ====
log_step "STEP 5/8: Building Docker Images"

log_info "Building all images (this may take a few minutes)..."
if $COMPOSE_CMD build --parallel 2>&1 | tail -20; then
    log_success "All images built successfully"
else
    log_error "Build failed! Check errors above."
    exit 1
fi

# ==== STEP 6: Launch ====
log_step "STEP 6/8: Launching Services"

log_info "Starting all services..."
$COMPOSE_CMD up -d

# Wait for services to be healthy
log_info "Waiting for services to be ready..."
MAX_WAIT=60
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    REDIS_HEALTHY=$($COMPOSE_CMD ps redis 2>/dev/null | grep -c "healthy" || true)
    if [ "$REDIS_HEALTHY" -ge 1 ]; then
        break
    fi
    sleep 2
    WAITED=$((WAITED + 2))
    echo -ne "\r  ⏳ Waiting... ${WAITED}s/${MAX_WAIT}s"
done
echo ""

if [ $WAITED -ge $MAX_WAIT ]; then
    log_warn "Timeout waiting for Redis healthcheck — continuing anyway"
else
    log_success "Redis is healthy"
fi

# Brief pause for all services to initialize
sleep 5
log_success "All services launched"

# ==== STEP 7: Verification Tests ====
log_step "STEP 7/8: Running Verification Tests"

# Unit tests
log_info "Running unit tests..."
if $COMPOSE_CMD run --rm bot pytest tests/ -v 2>&1; then
    log_success "Unit tests PASSED"
else
    log_warn "Unit tests FAILED — check test output above"
    ERRORS=$((ERRORS + 1))
fi

# Setup testnet verification
log_info "Running testnet setup verification..."
if $COMPOSE_CMD run --rm bot python scripts/setup_testnet.py 2>&1; then
    log_success "Testnet verification PASSED"
else
    log_warn "Testnet verification FAILED — check output above"
    ERRORS=$((ERRORS + 1))
fi

# API health check
log_info "Checking API health..."
sleep 3
if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
    log_success "API is responding"
else
    log_warn "API health check failed (may still be starting)"
fi

# ==== STEP 8: Summary ====
log_step "STEP 8/8: Deploy Summary"

echo ""
echo -e "${BOLD}📊 Container Status:${NC}"
$COMPOSE_CMD ps
echo ""

echo -e "${BOLD}🔗 Access Points:${NC}"
echo "  📊 Dashboard:     http://localhost:3000"
echo "  🔌 API:           http://localhost:8000"
echo "  📋 API Docs:      http://localhost:8000/docs"
echo "  ❤️  Health Check:  http://localhost:8000/health"
echo ""

if [ "$ERRORS" -gt 0 ]; then
    echo -e "${YELLOW}${BOLD}⚠️  Deploy completed with $ERRORS warning(s).${NC}"
    echo "   Check the output above for details."
else
    echo -e "${GREEN}${BOLD}✅ Deploy completed successfully!${NC}"
fi

echo ""
echo -e "${BOLD}📝 Useful Commands:${NC}"
echo "  ./scripts/logs.sh bot       — View bot logs"
echo "  ./scripts/status.sh         — Check service status"
echo "  ./scripts/stop.sh           — Stop all services"
echo "  ./scripts/emergency-stop.sh — Emergency stop"
echo ""
