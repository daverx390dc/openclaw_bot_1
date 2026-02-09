#!/bin/bash
# Quick restart script

cd "$(dirname "$0")"

echo "🔄 Restarting bot..."

# Stop
bash stop_bot.sh

# Wait
sleep 2

# Start
bash start_bot.sh
