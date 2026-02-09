import ccxt
import time

print("CCXT version:", ccxt.__version__)  # Should be recent (4.5.x+)

# ────────────────────────────────────────────────
# >>> REPLACE WITH YOUR REAL LIVE KEYS <<<
# From https://www.binance.com/en/my/settings/api-management
# ────────────────────────────────────────────────
API_KEY ='NQo2tPg48uSuMpYMtvRJMv151DaVrkNKL7k5rhdBTquf2x1AcMMFZNp6O89SZt6T'
API_SECRET = 'UNbsxuvoOOZeKLcYs4VDAl4ZAqZeXB6VCSbGpIxAbzLWl8HqCmB4KYumxMYLcxBe'

try:
    exchange = ccxt.binanceusdm({
        'apiKey': API_KEY,
        'secret': API_SECRET,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'future',           # perpetual USDT-margined futures
            'adjustForTimeDifference': True,   # avoids timestamp sync issues
        },
        'verbose': False,                      # set True to see full request logs
    })

    print("Running in LIVE mode — real Binance Futures[](https://fapi.binance.com)")

    # Show active endpoints for confirmation
    print("\nBase API URL →", exchange.urls['api'])
    print("FAPI private →", exchange.urls.get('api', {}).get('fapiPrivate', 'N/A'))

    # ─── Basic live tests ───────────────────────────────────────
    print("\n1. Fetch server time ...")
    server_time = exchange.fetch_time()
    print(f"Server time: {time.ctime(server_time / 1000)}")

    print("\n2. Fetch futures balance ...")
    # Use params to ensure futures wallet is queried
    balance = exchange.fetch_balance(params={'type': 'future'})

    print("Balance keys:", list(balance.keys()))
    usdt_info = balance.get('USDT', {})
    print(f"USDT → free: {usdt_info.get('free', 0):,.2f} | used: {usdt_info.get('used', 0):,.2f} | total: {usdt_info.get('total', 0):,.2f}")

    if usdt_info.get('total', 0) == 0:
        print("→ No USDT in futures wallet (normal if empty — transfer from spot first)")

    print("\n3. ETH/USDT:USDT ticker ...")
    ticker = exchange.fetch_ticker('ETH/USDT:USDT')
    print(f"Last price: {ticker['last']:.2f} USDT")

    print("\n✅ Live connection & authentication successful!")

except ccxt.AuthenticationError as e:
    print("\n❌ Auth error — check keys, IP whitelist, futures permissions:", e)
except ccxt.NetworkError as e:
    print("\nNetwork / connectivity issue:", e)
except Exception as e:
    print("\nOther error:", type(e).__name__, "→", str(e))

print("\nDone.")