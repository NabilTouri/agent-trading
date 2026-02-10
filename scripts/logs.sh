#!/bin/bash
# =============================================================================
# logs.sh — Log Viewer
# AI Trading Bot Multi-Agent
# Usage: ./logs.sh                 (all services, last 50 lines)
#        ./logs.sh bot             (only bot logs)
#        ./logs.sh bot 200         (last 200 lines)
#        ./logs.sh -f bot          (follow bot logs)
#        ./logs.sh -f              (follow all logs)
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

if docker compose version &>/dev/null; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &>/dev/null; then
    COMPOSE_CMD="docker-compose"
else
    echo "Docker Compose not found!"
    exit 1
fi

# Parse arguments
FOLLOW=false
SERVICE=""
LINES=50

while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--follow) FOLLOW=true; shift ;;
        -h|--help)
            echo "Usage: ./logs.sh [OPTIONS] [SERVICE] [LINES]"
            echo ""
            echo "Services: bot, api, redis, dashboard, backup-cron"
            echo ""
            echo "Options:"
            echo "  -f, --follow     Follow logs in real-time"
            echo "  -h, --help       Show this help"
            echo ""
            echo "Examples:"
            echo "  ./logs.sh              All services, last 50 lines"
            echo "  ./logs.sh bot          Bot logs, last 50 lines"
            echo "  ./logs.sh bot 200      Bot logs, last 200 lines"
            echo "  ./logs.sh -f bot       Follow bot logs"
            exit 0
            ;;
        [0-9]*) LINES="$1"; shift ;;
        *) SERVICE="$1"; shift ;;
    esac
done

# Build command
CMD="$COMPOSE_CMD logs --tail $LINES"
if [ "$FOLLOW" = true ]; then
    CMD="$CMD -f"
fi
if [ -n "$SERVICE" ]; then
    CMD="$CMD $SERVICE"
fi

echo "📋 Showing logs (tail=$LINES, follow=$FOLLOW, service=${SERVICE:-all})"
echo "   Press Ctrl+C to exit"
echo ""

exec $CMD
