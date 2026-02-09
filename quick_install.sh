#!/bin/bash
# Quick install script - installs Python packages only (assumes system packages exist)

echo "🚀 Quick Install - Python Packages Only"
echo ""

cd /home/ubuntu/.openclaw/workspace/crypto-trading-bot

# Upgrade pip
echo "📦 Upgrading pip..."
python3 -m pip install --upgrade pip -q

# Install Python packages
echo "📦 Installing ccxt..."
pip3 install ccxt --upgrade

echo "📦 Installing pandas and numpy..."
pip3 install pandas numpy

echo "📦 Installing TA-Lib (Python wrapper)..."
# Try to install TA-Lib, if it fails, install system dependencies first
if pip3 install TA-Lib 2>/dev/null; then
    echo "✅ TA-Lib installed successfully"
else
    echo "⚠️ TA-Lib needs system library. Installing..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq build-essential wget python3-dev
    
    # Install TA-Lib C library
    cd /tmp
    wget -q http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
    tar -xzf ta-lib-0.4.0-src.tar.gz
    cd ta-lib/
    ./configure --prefix=/usr
    make -j$(nproc)
    sudo make install
    sudo ldconfig
    cd /home/ubuntu/.openclaw/workspace/crypto-trading-bot
    pip3 install TA-Lib
fi

echo ""
echo "🔍 Verifying installations..."
python3 -c "import ccxt; print(f'✅ ccxt {ccxt.__version__}')"
python3 -c "import pandas; print(f'✅ pandas {pandas.__version__}')"
python3 -c "import numpy; print(f'✅ numpy {numpy.__version__}')"
python3 -c "import talib; print(f'✅ talib installed')"

echo ""
echo "✅ Installation complete!"
echo "🚀 Now run: bash start_bot.sh"
