#!/usr/bin/env python3
"""
Check Binance Testnet Balance
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import ccxt.pro as ccxtpro
from config.api_keys import API_KEY, API_SECRET

async def check_balance():
    """Check USDT balance on Binance testnet"""
    exchange = ccxtpro.binanceusdm({
        'apiKey': API_KEY,
        'secret': API_SECRET,
        'enableRateLimit': True,
    })
    exchange.enableDemoTrading(True)
    
    try:
        print("Connecting to Binance Testnet...")
        balance = await exchange.fetch_balance()
        
        usdt = balance.get('USDT', {})
        free = usdt.get('free', 0)
        used = usdt.get('used', 0)
        total = usdt.get('total', 0)
        
        print("\n" + "="*60)
        print("BINANCE TESTNET BALANCE")
        print("="*60)
        print(f"Free (Available):  ${free:,.2f} USDT")
        print(f"Used (In Orders):  ${used:,.2f} USDT")
        print(f"Total:             ${total:,.2f} USDT")
        print("="*60)
        print(f"\nPosition Size Per Trade: $500 USDT")
        print(f"Can Open: {int(free / 500)} more trades\n")
        
        # Check positions
        positions = await exchange.fetch_positions()
        active_positions = [p for p in positions if float(p.get('positionAmt', 0)) != 0]
        
        if active_positions:
            print("="*60)
            print("ACTIVE POSITIONS")
            print("="*60)
            for pos in active_positions:
                symbol = pos.get('symbol', 'N/A')
                amount = float(pos.get('positionAmt', 0))
                entry = float(pos.get('entryPrice', 0))
                unrealized = float(pos.get('unrealizedProfit', 0))
                side = 'LONG' if amount > 0 else 'SHORT'
                
                print(f"{symbol} {side}")
                print(f"  Entry: ${entry:.2f}")
                print(f"  Size: {abs(amount):.4f}")
                print(f"  Unrealized P&L: ${unrealized:+.2f}")
            print("="*60)
        else:
            print("No active positions\n")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await exchange.close()

if __name__ == "__main__":
    asyncio.run(check_balance())
