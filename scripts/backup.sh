#!/bin/bash
# =============================================================================
# backup.sh — Manual Backup (Redis + Logs)
# AI Trading Bot Multi-Agent
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
log_error()   { echo -e "${RED}[❌]${NC}    $1"; }

TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
BACKUP_DIR="backups/backup_${TIMESTAMP}"
KEEP_DAYS=7

echo -e "${BOLD}"
echo "╔═══════════════════════════════════════════════╗"
echo "║       💾 AI TRADING BOT — BACKUP              ║"
echo "╚═══════════════════════════════════════════════╝"
echo -e "${NC}"
echo "📅 $(date '+%Y-%m-%d %H:%M:%S')"
echo "📁 Backup dir: $BACKUP_DIR"
echo ""

# Create backup directory
mkdir -p "$BACKUP_DIR"

# ==== Redis Backup ====
echo -e "${CYAN}${BOLD}━━━ Redis Backup ━━━${NC}"

# Trigger Redis BGSAVE
if docker exec trading-redis redis-cli BGSAVE 2>/dev/null; then
    log_info "Redis BGSAVE triggered, waiting for completion..."
    sleep 3

    # Copy RDB file from container
    if docker cp trading-redis:/data/dump.rdb "$BACKUP_DIR/redis_dump.rdb" 2>/dev/null; then
        RDB_SIZE=$(du -sh "$BACKUP_DIR/redis_dump.rdb" | cut -f1)
        log_success "Redis dump saved ($RDB_SIZE)"
    else
        log_error "Could not copy Redis dump (container may not have data yet)"
    fi
else
    log_error "Could not trigger Redis backup (is Redis running?)"
fi

# ==== Logs Backup ====
echo ""
echo -e "${CYAN}${BOLD}━━━ Logs Backup ━━━${NC}"

if [ -d "logs" ] && [ "$(ls -A logs 2>/dev/null)" ]; then
    cp -r logs "$BACKUP_DIR/logs"
    LOGS_SIZE=$(du -sh "$BACKUP_DIR/logs" | cut -f1)
    log_success "Logs saved ($LOGS_SIZE)"
else
    log_info "No logs to backup"
fi

# ==== Docker Compose Logs ====
echo ""
echo -e "${CYAN}${BOLD}━━━ Docker Logs Snapshot ━━━${NC}"

if docker compose version &>/dev/null; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

$COMPOSE_CMD logs --tail 1000 > "$BACKUP_DIR/docker_logs.txt" 2>/dev/null && \
    log_success "Docker logs snapshot saved" || \
    log_info "No Docker logs to save"

# ==== .env Backup (masked) ====
echo ""
echo -e "${CYAN}${BOLD}━━━ Config Backup ━━━${NC}"

if [ -f ".env" ]; then
    # Save a masked version of .env for reference
    sed -E 's/(KEY|SECRET|TOKEN|PASSWORD|DSN)=.+/\1=***REDACTED***/g' .env > "$BACKUP_DIR/env_masked.txt"
    log_success "Config saved (API keys redacted)"
fi

# ==== Cleanup Old Backups ====
echo ""
echo -e "${CYAN}${BOLD}━━━ Cleanup ━━━${NC}"

if [ -d "backups" ]; then
    OLD_BACKUPS=$(find backups -maxdepth 1 -type d -name "backup_*" -mtime +${KEEP_DAYS} 2>/dev/null | wc -l)
    if [ "$OLD_BACKUPS" -gt 0 ]; then
        find backups -maxdepth 1 -type d -name "backup_*" -mtime +${KEEP_DAYS} -exec rm -rf {} +
        log_success "Removed $OLD_BACKUPS old backup(s) (older than ${KEEP_DAYS} days)"
    else
        log_info "No old backups to clean up"
    fi
fi

# ==== Summary ====
echo ""
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
echo -e "${GREEN}${BOLD}✅ Backup complete! ($TOTAL_SIZE)${NC}"
echo "📁 Location: $BACKUP_DIR"
echo ""

# List backup contents
ls -lh "$BACKUP_DIR"
echo ""
