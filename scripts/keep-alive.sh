#!/bin/bash
# Keep-alive script for Render.com free tier
# Prevents cold starts by pinging the service every 10 minutes
# Usage: Set up as a cron job on a free service like cron-job.org
# or run locally: */10 * * * * /path/to/keep-alive.sh

URL="https://nickberg-terminal.onrender.com/health"
LOG_FILE="/tmp/nickberg-keepalive.log"

# Simple ping with timeout
curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$URL" > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "$(date): Ping successful" >> "$LOG_FILE"
else
    echo "$(date): Ping failed" >> "$LOG_FILE"
fi
