#!/bin/bash
# Quick performance check - just cat the live dashboard

cd "$(dirname "$0")"

if [ ! -f "LIVE_PERFORMANCE.txt" ]; then
    echo "❌ LIVE_PERFORMANCE.txt not found!"
    echo "Start the bot with: ./start_with_monitoring.sh"
    exit 1
fi

clear
cat LIVE_PERFORMANCE.txt

echo ""
echo "🔄 Auto-refreshing... (Press Ctrl+C to stop)"
echo ""

# Optional: watch mode
if command -v watch > /dev/null 2>&1; then
    watch -n 5 cat LIVE_PERFORMANCE.txt
else
    # Fallback: manual refresh loop
    while true; do
        sleep 5
        clear
        cat LIVE_PERFORMANCE.txt
        echo ""
        echo "🔄 Auto-refreshing every 5 seconds... (Press Ctrl+C to stop)"
        echo ""
    done
fi
