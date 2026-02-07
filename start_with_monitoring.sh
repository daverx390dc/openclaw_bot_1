#!/bin/bash
# Start trading bot with live performance monitoring

echo "════════════════════════════════════════════════════════════"
echo "CRYPTO TRADING BOT - STARTING WITH LIVE MONITORING"
echo "════════════════════════════════════════════════════════════"
echo ""

cd "$(dirname "$0")"

# Check if bot is already running
if pgrep -f "agent.py" > /dev/null; then
    echo "⚠️  Bot agent is already running!"
    echo "Stop it first: pkill -f agent.py"
    exit 1
fi

if pgrep -f "performance_tracker.py" > /dev/null; then
    echo "⚠️  Performance tracker is already running!"
    echo "Stop it first: pkill -f performance_tracker.py"
    exit 1
fi

# Start the trading bot agent
echo "🚀 Starting trading bot agent..."
nohup python3 agent.py > logs/agent_console.log 2>&1 &
BOT_PID=$!
echo "   Bot PID: $BOT_PID"
sleep 2

# Verify bot started
if ! pgrep -f "agent.py" > /dev/null; then
    echo "❌ Failed to start bot agent!"
    exit 1
fi

# Start the performance tracker
echo "📊 Starting performance tracker..."
nohup python3 utils/performance_tracker.py > logs/performance_tracker.log 2>&1 &
TRACKER_PID=$!
echo "   Tracker PID: $TRACKER_PID"
sleep 1

# Verify tracker started
if ! pgrep -f "performance_tracker.py" > /dev/null; then
    echo "❌ Failed to start performance tracker!"
    echo "⚠️  Bot is still running. Stop it with: pkill -f agent.py"
    exit 1
fi

echo ""
echo "✅ All systems started successfully!"
echo ""
echo "════════════════════════════════════════════════════════════"
echo "MONITORING"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "📊 Live Performance Dashboard:"
echo "   cat LIVE_PERFORMANCE.txt"
echo ""
echo "📝 Bot Logs:"
echo "   tail -f logs/agent.log"
echo ""
echo "🔍 State Debug:"
echo "   tail -f logs/state_debug.log"
echo ""
echo "💰 Trade Log:"
echo "   tail -f logs/trades/trade_log.txt"
echo ""
echo "════════════════════════════════════════════════════════════"
echo "TO STOP"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "pkill -f agent.py && pkill -f performance_tracker.py"
echo ""
echo "════════════════════════════════════════════════════════════"
echo ""
echo "✅ Bot is now running autonomously!"
echo "   Performance updates every 10 seconds in LIVE_PERFORMANCE.txt"
echo ""
