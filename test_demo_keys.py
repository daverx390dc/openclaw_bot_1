#!/usr/bin/env python3
"""Test Binance Demo Trading API keys"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.api_keys import API_KEY, API_SECRET
import ccxt

print("=" * 60)
print("Testing Binance Demo Trading API Keys")
print("=" * 60)
print()

print(f"✓ API_KEY length: {len(API_KEY)}")
print(f"✓ API_SECRET length: {len(API_SECRET)}")
print(f"✓ API_KEY (first 10 chars): {API_KEY[:10]}...")
print()

try:
    print("Initializing exchange (demo mode)...")
    exchange = ccxt.binanceusdm({
        'apiKey': API_KEY,
        'secret': API_SECRET,
        'enableRateLimit': True,
        'options': {'defaultType': 'future'}
    })
    
    # Enable demo/testnet mode
    exchange.set_sandbox_mode(True)
    
    print(f"✓ Demo mode enabled")
    print(f"✓ API URL: {exchange.urls.get('api', 'N/A')}")
    print()
    
    print("Fetching balance...")
    balance = exchange.fetch_balance()
    
    print("=" * 60)
    print("✅ SUCCESS! Demo API keys are VALID!")
    print("=" * 60)
    print()
    
    usdt_info = balance.get('USDT', {})
    print(f"USDT Balance:")
    print(f"  Free: {usdt_info.get('free', 'N/A')} USDT")
    print(f"  Total: {usdt_info.get('total', 'N/A')} USDT")
    print()
    
    print("✓ Bot is ready to start!")
    print()
    
except Exception as e:
    print("=" * 60)
    print("❌ ERROR! Demo API keys are INVALID")
    print("=" * 60)
    print()
    print(f"Error: {str(e)}")
    print()
    print("Please check:")
    print("1. Keys are from demo.binance.com (not regular Binance)")
    print("2. Keys are copied correctly without spaces")
    print("3. Keys are not expired")
    print()
    sys.exit(1)
