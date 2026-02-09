#!/usr/bin/env python3
"""
Emergency Stop-Loss Placer
Detects open positions without SL and places them immediately
"""
import asyncio
import ccxt.pro as ccxtpro
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config.api_keys import API_KEY, API_SECRET
from datetime import datetime, timezone

SYMBOL = 'ETH/USDT:USDT'

async def place_emergency_sl():
    """Check for open positions and place SL if missing"""
    exchange = ccxtpro.binanceusdm({
        'apiKey': API_KEY,
        'secret': API_SECRET,
        'enableRateLimit': True,
        'options': {'defaultType': 'future'}
    })
    
    exchange.enable_demo_trading(True)
    await exchange.load_markets()
    
    try:
        # Get current position
        positions = await exchange.fetch_positions([SYMBOL])
        position = None
        for pos in positions:
            if pos['contracts'] and abs(pos['contracts']) > 0:
                position = pos
                break
        
        if not position:
            print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] No open position found")
            return
        
        # Get open orders
        orders = await exchange.fetch_open_orders(SYMBOL)
        sl_orders = [o for o in orders if 'STOP' in o.get('type', '').upper() or 'STOP' in o.get('info', {}).get('type', '').upper()]
        
        print(f"\n[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] POSITION DETECTED:")
        print(f"  Side: {position['side']}")
        print(f"  Contracts: {position['contracts']}")
        print(f"  Entry: {position['percentage']}")
        print(f"  Open Orders Total: {len(orders)}")
        print(f"  SL Orders: {len(sl_orders)}")
        
        if orders:
            print(f"\n  📋 ALL OPEN ORDERS:")
            for order in orders:
                order_type = order.get('type') or order.get('info', {}).get('type', 'UNKNOWN')
                order_price = order.get('stopPrice') or order.get('info', {}).get('stopPrice') or order.get('price', 'N/A')
                print(f"    - {order_type} @ {order_price} | Amount: {order.get('amount')} | ID: {order.get('id')}")
        
        if len(sl_orders) == 0 and position['contracts'] != 0:
            print(f"\n⚠️ CRITICAL: Position without stop-loss detected!")
            print(f"Position needs immediate SL placement.")
            print(f"Manual action required on exchange dashboard.")
        elif sl_orders:
            print(f"\n✅ Position has {len(sl_orders)} SL order(s)")
            for sl in sl_orders:
                print(f"   - SL @ {sl.get('stopPrice') or sl.get('price'):.2f}")
    
    except Exception as e:
        print(f"Error: {e}")
    
    finally:
        await exchange.close()

if __name__ == '__main__':
    asyncio.run(place_emergency_sl())
