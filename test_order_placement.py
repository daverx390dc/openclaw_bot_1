#!/usr/bin/env python3
"""
Test Order Placement - Manual BUY & EXIT
Verifies the bot can execute real orders on Binance Futures
"""
import ccxt
import time
import sys
sys.path.append('.')
from config.api_keys import API_KEY, API_SECRET

print("="*60)
print("TEST ORDER PLACEMENT - 5 Second Test Trade")
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
    # Get current price
    print("\n[1/5] Fetching ETH price...")
    ticker = exchange.fetch_ticker('ETH/USDT:USDT')
    current_price = ticker['last']
    print(f"      Current ETH price: ${current_price:.2f}")
    
    # Calculate order size: 50 USDT / price / 30x leverage
    position_size_usdt = 50
    leverage = 30
    qty = (position_size_usdt / current_price) * leverage
    qty = round(qty, 4)
    print(f"\n[2/5] Order details:")
    print(f"      Position size: {position_size_usdt} USDT")
    print(f"      Leverage: {leverage}x")
    print(f"      Quantity: {qty} ETH")
    
    # Place BUY order
    print(f"\n[3/5] Placing BUY order at ${current_price:.2f}...")
    order = exchange.create_order(
        'ETH/USDT:USDT',
        'MARKET',
        'buy',
        qty,
        None,
        {'leverage': leverage}
    )
    order_id = order['id']
    print(f"      ✓ Order placed! ID: {order_id}")
    print(f"      Status: {order['status']}")
    
    # Wait 5 seconds
    print(f"\n[4/5] Waiting 5 seconds...")
    for i in range(5, 0, -1):
        print(f"      {i}s...", end='\r', flush=True)
        time.sleep(1)
    print("      Done!        ")
    
    # Close the position with SELL order
    print(f"\n[5/5] Closing position with SELL order...")
    close_order = exchange.create_order(
        'ETH/USDT:USDT',
        'MARKET',
        'sell',
        qty,
        None,
        {'reduceOnly': True}
    )
    print(f"      ✓ Position closed! ID: {close_order['id']}")
    print(f"      Status: {close_order['status']}")
    
    print("\n" + "="*60)
    print("✅ TEST TRADE SUCCESSFUL!")
    print("="*60)
    print("\nBot is ready for real trading signals.\n")
    
except Exception as e:
    print(f"\n❌ ERROR: {type(e).__name__}")
    print(f"   {str(e)}\n")
    sys.exit(1)
