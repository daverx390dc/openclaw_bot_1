#!/bin/bash
# Start the autonomous trading bot with venv activation

cd "$(dirname "$0")" || { echo "Failed to cd"; exit 1; }

# Kill existing processes
echo "Stopping any existing bot instances..."
pkill -f "agent.py" 2>/dev/null || true
pkill -f "unified_trading_bot" 2>/dev/null || true
sleep 2

# Archive logs with timestamp
echo "Archiving old logs..."
if [ -f logs/agent.log ]; then
    mv logs/agent.log logs/agent.log.$(date +%Y%m%d_%H%M%S).old 2>/dev/null
fi

# Use your actual venv name
VENV_DIR="venv"

if [ ! -d "$VENV_DIR" ] || [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo "❌ Virtual environment '$VENV_DIR' not found!"
    echo "Run: python3 -m venv $VENV_DIR && source $VENV_DIR/bin/activate && pip install ccxt pandas numpy"
    exit 1
fi

# Launch agent INSIDE activated venv + redirect output
echo "Starting agent inside venv..."
nohup bash -c "
    source $VENV_DIR/bin/activate
    echo \"[$(date '+%Y-%m-%d %H:%M:%S')] Agent starting with Python: \$(which python)\"
    echo \"ccxt check: \$(python -c 'import ccxt; print(ccxt.__version__)' 2>&1 || echo 'ccxt NOT found')\"
    python3 agent.py
" > logs/agent.log 2>&1 &
AGENT_PID=$!

sleep 3

if ps -p $AGENT_PID > /dev/null; then
    echo "✅ Agent launched (PID: $AGENT_PID)"
    echo "Venv used: $(realpath $VENV_DIR)"
    echo ""
    echo "Monitor:"
    echo "  tail -f logs/agent.log"
    echo ""
    echo "Stop: pkill -f agent.py"
else
    echo "❌ Failed to start — last log lines:"
    tail -n 30 logs/agent.log
    exit 1
fi