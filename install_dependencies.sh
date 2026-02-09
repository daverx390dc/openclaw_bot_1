#!/bin/bash
# Install all dependencies for the trading bot

echo "🔧 Installing Trading Bot Dependencies..."
echo ""

# Update package list
echo "📦 Updating package list..."
sudo apt-get update -qq

# Install system dependencies for TA-Lib
echo "📦 Installing system dependencies..."
sudo apt-get install -y -qq build-essential wget python3-pip python3-dev

# Install TA-Lib C library
if [ ! -f "/usr/local/lib/libta_lib.so" ]; then
    echo "📦 Installing TA-Lib C library..."
    cd /tmp
    wget -q http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
    tar -xzf ta-lib-0.4.0-src.tar.gz
    cd ta-lib/
    ./configure --prefix=/usr
    make -j$(nproc)
    sudo make install
    cd ..
    rm -rf ta-lib ta-lib-0.4.0-src.tar.gz
    echo "✅ TA-Lib C library installed"
else
    echo "✅ TA-Lib C library already installed"
fi

# Return to bot directory
cd /home/node/.openclaw/workspace/crypto-trading-bot

# Upgrade pip
echo "📦 Upgrading pip..."
python3 -m pip install --upgrade pip -q

# Install Python packages
echo "📦 Installing Python packages..."
pip3 install ccxt --upgrade -q
pip3 install pandas numpy -q
pip3 install TA-Lib -q

# Verify installations
echo ""
echo "🔍 Verifying installations..."
python3 -c "import ccxt; print(f'✅ ccxt {ccxt.__version__}')" 2>/dev/null || echo "❌ ccxt failed"
python3 -c "import pandas; print(f'✅ pandas {pandas.__version__}')" 2>/dev/null || echo "❌ pandas failed"
python3 -c "import numpy; print(f'✅ numpy {numpy.__version__}')" 2>/dev/null || echo "❌ numpy failed"
python3 -c "import talib; print(f'✅ talib installed')" 2>/dev/null || echo "❌ talib failed"

echo ""
echo "✅ All dependencies installed!"
echo ""
echo "🚀 Now run: bash start_bot.sh"
