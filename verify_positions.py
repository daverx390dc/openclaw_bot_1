#!/usr/bin/env python3
"""
Verify Actual Positions & Orders on Binance Futures
Check what the API really shows vs what bot reports
"""
import ccxt
import sys
sys.path.append('.')
from config.api_keys import API_KEY, API_SECRET
import json

print("="*60)
print("VERIFY LIVE POSITIONS & ORDERS")
print("="*60)

exchange = ccxt.binanceusdm({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'enableRateLimit': True,
    'options': {
        'defaultType': 'future',
        'adjustForTimeDifference': True,
    },
    'verbose': False,
})

try:
    # Fetch positions
    print("\n[1/3] Fetching open positions...")
    positions = exchange.fetch_positions(['ETH/USDT:USDT'])
    print(f"      Total positions: {len(positions)}")
    
    if positions:
        for pos in positions:
            print(f"\n      Symbol: {pos['symbol']}")
            print(f"        Contracts: {pos['contracts']}")
            print(f"        Collateral: {pos.get('collateral', 'N/A')}")
            print(f"        Percentage: {pos.get('percentage', 'N/A')}")
            print(f"        Side: {pos.get('side', 'N/A')}")
            print(f"        Entry Price: {pos.get('entryPrice', 'N/A')}")
            print(f"        Mark Price: {pos.get('markPrice', 'N/A')}")
            print(f"        Liquidation: {pos.get('liquidationPrice', 'N/A')}")
    else:
        print("      ✓ No open positions")
    
    # Fetch open orders
    print("\n[2/3] Fetching open orders...")
    orders = exchange.fetch_open_orders('ETH/USDT:USDT')
    print(f"      Total open orders: {len(orders)}")
    
    if orders:
        for order in orders:
            print(f"\n      Order ID: {order['id']}")
            print(f"        Type: {order['type']}")
            print(f"        Side: {order['side']}")
            print(f"        Amount: {order['amount']}")
            print(f"        Price: {order['price']}")
            print(f"        Status: {order['status']}")
    else:
        print("      ✓ No open orders")
    
    # Fetch balance
    print("\n[3/3] Fetching wallet balance...")
    balance = exchange.fetch_balance(params={'type': 'future'})
    if 'USDT' in balance:
        usdt = balance['USDT']
        print(f"      USDT Futures Balance:")
        print(f"        Free: {usdt.get('free', 0):.2f}")
        print(f"        Used: {usdt.get('used', 0):.2f}")
        print(f"        Total: {usdt.get('total', 0):.2f}")
    
    print("\n" + "="*60)
    print("VERIFICATION COMPLETE")
    print("="*60 + "\n")
    
except Exception as e:
    print(f"\n❌ ERROR: {type(e).__name__}")
    print(f"   {str(e)}\n")
    sys.exit(1)
