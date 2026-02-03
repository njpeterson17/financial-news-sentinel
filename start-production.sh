#!/bin/bash
# Production startup script for Nickberg Terminal
# Usage: ./start-production.sh [web|scraper]

set -e

MODE=${1:-web}
PORT=${PORT:-5000}

echo "=========================================="
echo "Nickberg Terminal - Production Startup"
echo "=========================================="
echo "Mode: $MODE"
echo "Port: $PORT"
echo ""

# Ensure data directory exists
mkdir -p data logs

# Set environment defaults if not set
export FLASK_ENV=${FLASK_ENV:-production}
export PYTHONUNBUFFERED=1

case "$MODE" in
    web)
        echo "Starting web dashboard..."
        cd web
        exec gunicorn app:app \
            --bind 0.0.0.0:$PORT \
            --workers 2 \
            --threads 4 \
            --timeout 120 \
            --access-logfile - \
            --error-logfile - \
            --capture-output \
            --enable-stdio-inheritance
        ;;
    
    scraper)
        echo "Starting background scraper..."
        cd src
        exec python main.py run
        ;;
    
    *)
        echo "Usage: $0 [web|scraper]"
        exit 1
        ;;
esac
