#!/bin/bash
# Start Nickberg Terminal Web Dashboard locally

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment
source .venv/bin/activate

# Change to web directory
cd web

echo "=========================================="
echo "  Nickberg Terminal - Web Dashboard"
echo "=========================================="
echo ""
echo "Starting server on http://localhost:5000"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Start the Flask app
python app.py
