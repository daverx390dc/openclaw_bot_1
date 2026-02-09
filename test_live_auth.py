#!/usr/bin/env python3
"""
Test Live Binance Futures Authentication
Verifies real production API keys work
"""
import ccxt
import time

print("CCXT version:", ccxt.__version__)  # Should be 4.5.x+

# ─── LIVE BINANCE USDⓈ-M FUTURES KEYS ───
API_KEY = 'NQo2tPg48uSuMpYMtvRJMv151DaVrkNKL7k5rhdBTquf2x1AcMMFZNp6O89SZt6T'
API_SECRET = 'UNbsxuvoOOZeKLcYs4VDAl4ZAqZeXB6VCSbGpIxAbzLWl8HqCmB4KYumxMYLcxBe'

try:
    exchange = ccxt.binanceusdm({
        'apiKey': API_KEY,
        'secret': API_SECRET,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'future',  # perpetual USDT-margined futures
            'adjustForTimeDifference': True,  # avoid timestamp sync issues
        },
        'verbose': False,
    })
    
    print("\n🔗 Running in LIVE mode — real Binance Futures")
    print("   Base API URL →", exchange.urls['api']['fapi'] if 'fapi' in exchange.urls.get('api', {}) else exchange.urls['api'])
    
    # Test 1: Server time
    print("\n[1/4] Fetching server time...")
    server_time = exchange.fetch_time()
    print(f"      ✓ Server time: {time.ctime(server_time / 1000)}")
    
    # Test 2: Futures balance
    print("\n[2/4] Fetching futures wallet balance...")
    balance = exchange.fetch_balance(params={'type': 'future'})
    
    if 'USDT' in balance:
        usdt = balance['USDT']
        print(f"      ✓ USDT balance:")
        print(f"        Free:  {usdt.get('free', 0):,.2f}")
        print(f"        Used:  {usdt.get('used', 0):,.2f}")
        print(f"        Total: {usdt.get('total', 0):,.2f}")
    else:
        print(f"      ⚠ USDT not found in balance. Keys available: {list(balance.keys())}")
    
    # Test 3: ETH/USDT ticker
    print("\n[3/4] Fetching ETH/USDT:USDT ticker...")
    ticker = exchange.fetch_ticker('ETH/USDT:USDT')
    print(f"      ✓ Last price: ${ticker['last']:.2f}")
    
    # Test 4: Open positions
    print("\n[4/4] Fetching open positions...")
    positions = exchange.fetch_positions(['ETH/USDT:USDT'])
    if positions:
        print(f"      Positions found: {len(positions)}")
        for pos in positions:
            print(f"        Symbol: {pos['symbol']}, Contracts: {pos['contracts']}")
    else:
        print(f"      ✓ No open positions (clean state)")
    
    print("\n" + "="*60)
    print("✅ LIVE AUTHENTICATION SUCCESSFUL!")
    print("="*60)
    print("\nAPI keys are valid. Bot can now trade on LIVE Binance Futures.")
    print("\n⚠️  WARNING: You are now connected to REAL trading!")
    print("    This bot WILL execute real trades with REAL funds.")
    print("    Start bot only when confident in strategy.")
    
except ccxt.AuthenticationError as e:
    print(f"\n❌ AUTH ERROR — Check API keys, IP whitelist, or permissions:")
    print(f"   {e}")
    
except ccxt.NetworkError as e:
    print(f"\n❌ NETWORK ERROR — Connectivity issue:")
    print(f"   {e}")
    
except Exception as e:
    print(f"\n❌ ERROR — {type(e).__name__}:")
    print(f"   {str(e)}")

print("\nDone.\n")
