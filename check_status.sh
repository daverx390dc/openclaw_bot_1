#!/bin/bash
# Check bot status

echo "════════════════════════════════════════════════════════════"
echo "Trading Bot Status Check"
echo "════════════════════════════════════════════════════════════"
echo ""

# Check if agent is running
if ps aux | grep "agent.py" | grep -v grep > /dev/null; then
    AGENT_PID=$(ps aux | grep "agent.py" | grep -v grep | awk '{print $2}')
    echo "✅ Agent: RUNNING (PID: $AGENT_PID)"
else
    echo "❌ Agent: NOT RUNNING"
fi

# Check if bot is running
if ps aux | grep "unified_trading_bot" | grep -v grep > /dev/null; then
    BOT_PID=$(ps aux | grep "unified_trading_bot" | grep -v grep | awk '{print $2}')
    echo "✅ Bot: RUNNING (PID: $BOT_PID)"
else
    echo "❌ Bot: NOT RUNNING"
fi

echo ""
echo "Recent logs:"
echo "────────────────────────────────────────────────────────────"
tail -10 logs/agent.log 2>/dev/null || echo "No logs found"
echo ""

# Check for recent trades
if [ -f "logs/trades/trade_log.txt" ]; then
    TRADE_COUNT=$(tail -n +2 logs/trades/trade_log.txt 2>/dev/null | wc -l)
    echo "Total trades: $TRADE_COUNT"
    echo ""
    echo "Last 3 trades:"
    echo "────────────────────────────────────────────────────────────"
    tail -3 logs/trades/trade_log.txt 2>/dev/null || echo "No trades yet"
fi

echo ""
echo "════════════════════════════════════════════════════════════"
