#!/bin/bash
# Quick start script for the crypto trading bot

echo "════════════════════════════════════════════════════════════"
echo "CRYPTO TRADING BOT - AUTONOMOUS AGENT"
echo "════════════════════════════════════════════════════════════"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.8+"
    exit 1
fi

# Check dependencies
echo "Checking dependencies..."
python3 -c "import ccxt, pandas, numpy, talib" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  Missing dependencies. Install with:"
    echo "   pip install -r requirements.txt"
    echo ""
    read -p "Install now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        pip install -r requirements.txt
    else
        exit 1
    fi
fi

# Check API keys
if grep -q "xxf5dG3dZBqOHRheU61t06pieHnkIfL0rlJVSTrDNFwtM35X8vPS4P2yOGfdy4J8" config/api_keys.py 2>/dev/null; then
    echo "⚠️  WARNING: Using exposed API keys!"
    echo "   Please update config/api_keys.py with new testnet keys"
    echo "   Get them from: https://testnet.binancefuture.com/"
    echo ""
fi

# Create necessary directories
mkdir -p logs/trades data

echo "✅ All checks passed"
echo ""
echo "Starting autonomous agent..."
echo "Press Ctrl+C to stop"
echo ""
echo "════════════════════════════════════════════════════════════"
echo ""

# Start the agent
python3 agent.py
