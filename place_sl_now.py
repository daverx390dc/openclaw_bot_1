#!/usr/bin/env python3
"""
EMERGENCY: Place SL for current open position
"""
import asyncio
import ccxt.pro as ccxtpro
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config.api_keys import API_KEY, API_SECRET
from datetime import datetime, timezone

SYMBOL = 'ETH/USDT:USDT'

async def place_sl_emergency():
    exchange = ccxtpro.binanceusdm({
        'apiKey': API_KEY,
        'secret': API_SECRET,
        'enableRateLimit': True,
        'options': {'defaultType': 'future'}
    })
    
    exchange.enable_demo_trading(True)
    await exchange.load_markets()
    
    try:
        # Get position
        positions = await exchange.fetch_positions([SYMBOL])
        position = None
        for pos in positions:
            if pos['contracts'] and abs(pos['contracts']) > 0:
                position = pos
                break
        
        if not position:
            print("No position found")
            return
        
        side = position['side']
        qty = abs(position['contracts'])
        current_price = position.get('info', {}).get('markPrice', 0)
        
        print(f"\n[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] EMERGENCY SL PLACEMENT")
        print(f"Position: {side.upper()} {qty} contracts")
        print(f"Current price: {current_price}")
        
        # Calculate SL: Entry was 2102.39, risk ~15.53
        # SL should be ~2086.86
        sl_price = 2086.86
        sl_side = 'sell' if side == 'long' else 'buy'
        
        print(f"Placing SL @ {sl_price:.2f} ({sl_side.upper()})")
        
        # Try STOP order with price parameter
        for attempt in range(3):
            try:
                print(f"  Attempt {attempt+1}/3...")
                
                sl_order = await exchange.create_order(
                    SYMBOL, 'STOP', sl_side, qty, sl_price,
                    {'stopPrice': sl_price, 'reduceOnly': True}
                )
                
                print(f"✅ SL ORDER PLACED!")
                print(f"   Order ID: {sl_order['id']}")
                print(f"   Type: STOP")
                print(f"   Price: {sl_price}")
                
                # Verify
                await asyncio.sleep(0.5)
                orders = await exchange.fetch_open_orders(SYMBOL)
                sl_exists = any(o['id'] == sl_order['id'] for o in orders)
                
                if sl_exists:
                    print(f"✅ VERIFIED: SL is in open orders")
                else:
                    print(f"⚠️ WARNING: SL created but not verified")
                
                break
            
            except Exception as e:
                print(f"  ❌ Attempt {attempt+1} failed: {e}")
                if attempt < 2:
                    await asyncio.sleep(1)
    
    except Exception as e:
        print(f"Error: {e}")
    
    finally:
        await exchange.close()

if __name__ == '__main__':
    asyncio.run(place_sl_emergency())
