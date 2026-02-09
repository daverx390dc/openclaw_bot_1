# SL Fix Testing Guide

## Quick Validation
Run this after restarting the bot to confirm the fix works:

### Test 1: Manual SL Order Test
```python
import asyncio
import ccxt.pro as ccxtpro
from config.api_keys import API_KEY, API_SECRET

async def test_sl_order():
    exchange = ccxtpro.binanceusdm({
        'apiKey': API_KEY,
        'secret': API_SECRET,
        'enableRateLimit': True,
        'options': {'defaultType': 'future'},
    })
    exchange.enableDemoTrading(True)
    
    await exchange.load_markets()
    
    # Test STOP_MARKET order creation (without actual position)
    # This will fail with "reduceOnly" but will show if syntax is correct
    try:
        order = await exchange.create_order(
            'ETH/USDT:USDT', 
            'STOP_MARKET', 
            'sell', 
            0.1,  # Small test qty
            None,  # No limit price
            {'stopPrice': 2000.0, 'reduceOnly': True}
        )
        print("✅ STOP_MARKET syntax accepted by API")
        print(f"Order: {order}")
    except Exception as e:
        if "reduceOnly" in str(e) or "position" in str(e).lower():
            print("✅ Syntax correct (failed due to no position, as expected)")
        else:
            print(f"❌ Syntax error: {e}")
    
    await exchange.close()

asyncio.run(test_sl_order())
```

### Test 2: Monitor Bot Logs
After restarting bot, watch for:

**SUCCESS indicators:**
```
✅ Initial SL placed @ 2086.86 (ID: 1000000011338052)
✅ SL verified in open orders
```

**FAILURE indicators (should NOT appear):**
```
❌ SL attempt 1 failed: InvalidOrder: binanceusdm createOrder() requires a price argument
❌ CRITICAL: SL placement failed after 3 attempts
```

### Test 3: Live Order Verification
```bash
# After bot enters a position, check orders:
tail -f logs/state_debug.log | grep -i "SL"
```

Expected output:
```
[TIME] SL placement attempt 1/3: price=2086.86, side=sell, qty=2.378
[TIME] SL order placed: 1000000011338052 @ 2086.86
[TIME] ✅ SL verified in open orders
```

### Test 4: Reconciliation Stability
- Let bot run for 5+ minutes with a position
- Check that reconciliation does NOT clear the position
- Verify SL order persists through multiple reconciliation cycles

Expected:
```
[TIME] === STATE RECONCILIATION START ===
[TIME] Exchange position: 2.378
[TIME] Internal position: long
[TIME] Open orders: 1
[TIME] === STATE RECONCILIATION COMPLETE ===
```

## If Tests Fail

### Still seeing "requires a price argument"?
- Check that file was saved correctly
- Restart the bot process
- Verify changes at lines 469 and 574

### Order placed but immediately cancelled?
- Different issue (Binance testnet API flakiness)
- Check Binance testnet status
- May need to switch to mainnet demo or live trading (with small amounts)

### Position cleared by reconciliation?
- Check if exchange actually shows the position
- May indicate entry order isn't filling properly
- Verify balance and margin requirements

## Success Criteria
✅ SL orders place without errors  
✅ Orders appear in `fetch_open_orders()`  
✅ Orders persist through reconciliation  
✅ Trailing SL updates work  
✅ No "phantom position" clearing  

## Next Steps After Validation
1. Let bot run for 1 hour with monitoring
2. Verify at least 1 full trade cycle (entry → SL/TP → exit)
3. Check P&L matches expectations
4. If stable, remove detailed logging (optional)
5. Consider adding order confirmation webhooks
