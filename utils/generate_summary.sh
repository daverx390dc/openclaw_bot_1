#!/bin/bash
# generate_summary.sh - Creates a summary file you can share with me

OUTPUT_FILE="/tmp/bot_summary_$(date +%Y%m%d_%H%M%S).txt"

cd "$(dirname "$0")/.."

{
    echo "=================================="
    echo "CRYPTO BOT SUMMARY"
    echo "Generated: $(date)"
    echo "=================================="
    echo ""
    
    echo "--- BOT STATUS ---"
    python3 utils/status.py 2>/dev/null || echo "Status script not available"
    echo ""
    
    echo "--- AGENT HEALTH (Last 20 lines) ---"
    tail -20 logs/agent.log 2>/dev/null || echo "No agent log"
    echo ""
    
    echo "--- STATE DEBUG (Last 15 lines) ---"
    tail -15 logs/state_debug.log 2>/dev/null || echo "No state debug log"
    echo ""
    
    echo "--- RECENT TRADES (Last 5) ---"
    tail -6 logs/trades/trade_log.txt 2>/dev/null | tail -5 || echo "No trades yet"
    echo ""
    
    echo "--- CURRENT POSITION ---"
    if pgrep -f unified_trading_bot > /dev/null; then
        echo "✅ Bot is running"
    else
        echo "❌ Bot is NOT running"
    fi
    echo ""
    
    echo "=================================="
    echo "END SUMMARY"
    echo "=================================="
    
} > "$OUTPUT_FILE"

echo "Summary saved to: $OUTPUT_FILE"
echo ""
echo "To share with me, run:"
echo "  cat $OUTPUT_FILE"
