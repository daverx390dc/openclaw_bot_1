#!/bin/bash
# sync_to_openclaw.sh
# This creates a summary file in OpenClaw's workspace directory
# Run via cron: */30 * * * * /home/ubuntu/folder_1/crypto-trading-bot/utils/sync_to_openclaw.sh

# Directories
BOT_DIR="/home/ubuntu/folder_1/crypto-trading-bot"
OPENCLAW_WORKSPACE="/home/node/.openclaw/workspace/bot-logs"

# Try to create OpenClaw workspace directory
# (Will fail if on different machine, which is fine - we'll use alternative method)
mkdir -p "$OPENCLAW_WORKSPACE" 2>/dev/null

# Generate summary
SUMMARY_FILE="$OPENCLAW_WORKSPACE/bot_status_$(date +%Y%m%d_%H%M).txt"
LATEST_LINK="$OPENCLAW_WORKSPACE/latest_status.txt"

cd "$BOT_DIR"

{
    echo "=== CRYPTO BOT STATUS ==="
    echo "Timestamp: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
    echo "========================="
    echo ""
    
    # Bot health
    if pgrep -f unified_trading_bot > /dev/null; then
        echo "✅ Bot Status: RUNNING"
    else
        echo "❌ Bot Status: STOPPED"
    fi
    echo ""
    
    # Agent status
    echo "--- Agent Log (Last 10 lines) ---"
    tail -10 logs/agent.log 2>/dev/null || echo "No agent log"
    echo ""
    
    # State reconciliation
    echo "--- State Debug (Last 10 lines) ---"
    tail -10 logs/state_debug.log 2>/dev/null || echo "No state log"
    echo ""
    
    # Recent trades
    echo "--- Recent Trades (Last 3) ---"
    tail -4 logs/trades/trade_log.txt 2>/dev/null | tail -3 || echo "No trades yet"
    echo ""
    
    # P&L summary
    echo "--- P&L Summary ---"
    python3 utils/status.py 2>/dev/null | grep -E "(Total P&L|Uptime)" || echo "Status unavailable"
    
} > "$SUMMARY_FILE" 2>&1

# Create symlink to latest
ln -sf "$SUMMARY_FILE" "$LATEST_LINK" 2>/dev/null

# If OpenClaw workspace isn't accessible, save to /tmp
if [ ! -w "$OPENCLAW_WORKSPACE" ]; then
    TMP_SUMMARY="/tmp/openclaw_bot_status.txt"
    cp "$SUMMARY_FILE" "$TMP_SUMMARY" 2>/dev/null || cat > "$TMP_SUMMARY" <<EOF
Summary saved to: $SUMMARY_FILE
To share with OpenClaw, copy/paste this file or run:
  cat $SUMMARY_FILE
EOF
    echo "Summary saved to: $TMP_SUMMARY (OpenClaw workspace not accessible)"
else
    echo "Summary saved to: $SUMMARY_FILE"
    echo "OpenClaw can read: $LATEST_LINK"
fi
