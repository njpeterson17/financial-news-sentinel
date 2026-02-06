#!/bin/bash
# Start Nickberg Terminal Web Dashboard with WebSocket support

cd "$(dirname "$0")"

# Install dependencies if needed
pip install -q -r requirements.txt 2>/dev/null || pip install -q --break-system-packages -r requirements.txt 2>/dev/null

# Run the web app with SocketIO support
# Using python directly instead of flask run to enable WebSocket
cd web
export FLASK_APP=app.py
export FLASK_ENV=development

# Run with eventlet for WebSocket support
python3 app.py
