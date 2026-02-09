#!/bin/bash
# Stop the trading bot

echo "Stopping trading bot..."

# Kill agent (which will also stop the bot)
pkill -f "agent.py"
sleep 1

# Kill any remaining bot processes
pkill -f "unified_trading_bot"
sleep 1

# Check if stopped
if ps aux | grep -E "(agent.py|unified_trading_bot)" | grep -v grep > /dev/null; then
    echo "⚠️ Some processes still running. Force killing..."
    pkill -9 -f "agent.py"
    pkill -9 -f "unified_trading_bot"
    sleep 1
fi

if ps aux | grep -E "(agent.py|unified_trading_bot)" | grep -v grep > /dev/null; then
    echo "❌ Failed to stop bot"
    exit 1
else
    echo "✅ Bot stopped successfully"
fi
