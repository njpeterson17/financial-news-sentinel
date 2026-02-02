#!/bin/bash
# Start News Sentinel Bot Web Dashboard

cd "$(dirname "$0")"

# Install dependencies if needed
pip install -q -r requirements.txt 2>/dev/null || pip install -q --break-system-packages -r requirements.txt 2>/dev/null

# Run the web app
cd web
export FLASK_APP=app.py
export FLASK_ENV=development
python3 -m flask run --host=0.0.0.0 --port=5000
