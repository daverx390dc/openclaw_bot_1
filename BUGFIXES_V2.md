# Bug Fixes - V2

## Issues Identified

You reported three critical bugs:

1. **Signal detected but order not placed** - Timing mismatch
2. **Order placed but not exited** - Stop-loss not triggering
3. **Orphan orders** - Open orders exist with no position

These can cause:
- ❌ Missed profitable trades
- ❌ Unprotected positions (no stop-loss = unlimited loss)
- ❌ Multiple positions when expecting one
- ❌ Money loss

---

## Root Causes

### 1. Timing Issue (Signal → No Order)

**Problem:**
```python
# OLD CODE
if ts_dt != last_candle_time:  # New candle detected
    signal = detect_signal(price_df)  # But candle is still UPDATING!
    await place_entry(signal, price, atr)  # Price might change before order
```

**What happens:**
- Candle opens at `15:03:00`
- Bot sees "new candle" at `15:03:01` (1 second into it)
- Detects BUY signal based on partial data
- By the time order is placed (15:03:02), candle has updated
- Signal conditions no longer valid → order rejected or price wrong

**Fix:**
```python
# NEW CODE
if is_candle_closed(ts_dt, TIMEFRAME):  # Wait for 95% completion
    signal = detect_signal(price_df)  # Only act on COMPLETED candles
    await place_entry(signal, price, atr)
```

Now signals are only checked when the candle is 95% complete (last 9 seconds of a 3-minute candle).

---

### 2. Stop-Loss Not Triggering (Order → No Exit)

**Problem:**
```python
# OLD CODE
sl_order = await exchange.create_order(...)
stop_order_id = sl_order['id']
# ❌ Never verified if order was actually placed!
```

**What happens:**
- Order placement call returns success
- But exchange actually rejected it (rate limit, balance, etc.)
- Bot thinks SL exists, but it doesn't
- Position is UNPROTECTED

**Also:**
- Stop orders getting cancelled accidentally
- Multiple stop orders conflicting
- Internal state (`current_position`) doesn't match exchange reality

**Fix:**
```python
# NEW CODE
sl_order = await exchange.create_order(...)
stop_order_id = sl_order['id']

# VERIFY it was actually placed
await asyncio.sleep(0.5)
orders = await exchange.fetch_open_orders(SYMBOL)
sl_exists = any(o['id'] == stop_order_id for o in orders)
if not sl_exists:
    log_state(f"WARNING: SL order {stop_order_id} not found!")
    print(f"⚠️ Stop-loss order may not be active!")
```

Plus: **State Reconciliation** every 30 seconds checks if position has SL.

---

### 3. Orphan Orders (Orders with No Position)

**Problem:**
```python
# OLD CODE
# Bot crashes or restarts
# current_position = None (fresh state)
# But exchange still has orders from previous run!
```

**What happens:**
- Bot places BUY order + SL
- Bot crashes before recording position
- Bot restarts with `current_position = None`
- Exchange still has open SL order
- Next BUY signal → places ANOTHER order
- Now you have 2 positions when expecting 0 or 1

**Fix:**
```python
# NEW CODE: State Reconciliation
async def reconcile_state():
    # 1. Check exchange position
    exchange_position = await exchange.fetch_positions([SYMBOL])
    
    # 2. Check internal state
    internal_position = current_position
    
    # 3. Cross-check
    if exchange_position and not internal_position:
        # RECOVER: Bot doesn't know about position
        current_position = {...}  # Restore from exchange
    
    elif not exchange_position and internal_position:
        # CLEAR: Phantom position
        current_position = None
    
    # 4. Check orphan orders
    orders = await exchange.fetch_open_orders(SYMBOL)
    if not exchange_position and len(orders) > 0:
        # CLEANUP: Cancel old orders
        for order in orders:
            if age > 5_minutes:
                await cancel_order(order['id'])
```

Runs every **30 seconds** automatically.

---

## Key Changes in V2

### 1. Candle Close Detection

```python
CANDLE_CLOSE_THRESHOLD = 0.95  # Only act at 95% completion

def is_candle_closed(candle_timestamp, timeframe='3m'):
    """Only returns True when candle is nearly complete"""
    time_in_candle = current_time - candle_time
    progress = time_in_candle / timeframe_seconds
    return progress >= 0.95  # Last 9 seconds of 3-min candle
```

✅ **Result:** Signals only on stable, completed candles

---

### 2. State Reconciliation (Every 30s)

```python
RECONCILE_INTERVAL_SEC = 30

async def reconcile_state():
    """Cross-check bot state vs exchange reality"""
    
    # Check for desync
    # Recover unknown positions
    # Clear phantom positions
    # Cancel orphan orders (older than 5 min)
    # Verify stop-loss exists for active positions
```

✅ **Result:** Bot auto-fixes state issues

---

### 3. Order Verification

```python
# After placing ANY order
await asyncio.sleep(0.5)
orders = await exchange.fetch_open_orders(SYMBOL)
if order_id not in [o['id'] for o in orders]:
    log_state("WARNING: Order not found!")
```

✅ **Result:** Immediate detection of failed orders

---

### 4. Enhanced Logging

New debug log: `logs/state_debug.log`

```
[2026-02-07 15:45:00] === STATE RECONCILIATION START ===
[2026-02-07 15:45:00] Exchange position: 0.1538
[2026-02-07 15:45:00] Internal position: long
[2026-02-07 15:45:00] Open orders: 1
[2026-02-07 15:45:00] Found existing SL order: 12345 @ 3220.50
[2026-02-07 15:45:00] === STATE RECONCILIATION COMPLETE ===
```

✅ **Result:** Easy debugging of state issues

---

### 5. Defensive Order Management

**Before placing entry order:**
```python
# 1. Verify no position
has_no_position = await verify_no_position()
if not has_no_position:
    BLOCK_TRADE()

# 2. Cancel any orphan orders
await cancel_all_orders()

# 3. Place order
# 4. Verify it was placed
# 5. Place SL
# 6. Verify SL was placed
```

✅ **Result:** Multi-layer safety checks

---

## New Features

### 1. Automatic Position Recovery

If bot crashes and restarts:
```
⚠️ DESYNC DETECTED: Exchange has position we don't know about!
RECOVERY: Recovering position 0.1538 @ 3250.50
Found existing SL order: 67890 @ 3220.50
✅ Position and SL recovered
```

### 2. Orphan Order Cleanup

```
⚠️ ORPHAN ORDERS DETECTED: 2 orders with no position
CLEANUP: Cancelling 2 orphan orders
Cancelled orphan order: 11111 (age: 320s)
Cancelled orphan order: 22222 (age: 450s)
```

### 3. Missing Stop-Loss Detection

```
⚠️ CRITICAL: Position has NO STOP-LOSS!
RECOVERY: Placing emergency SL @ 3220.50
✅ Emergency SL placed
```

---

## How to Use V2

### Update Agent

Already done! `agent.py` now uses `unified_trading_bot_v2.py`

### Start Bot

```bash
./start.sh
```

Or:
```bash
python3 agent.py
```

### Monitor

**Trade log (same as before):**
```bash
tail -f logs/trades/trade_log.txt
```

**NEW: State debug log:**
```bash
tail -f logs/state_debug.log
```

Shows reconciliation checks, order verifications, state changes.

---

## Testing Checklist

To verify the fixes work:

### Test 1: Timing (Signal → Order)

**Before:** Signal at 15:03:01, order at 15:03:05, price changed
**After:** Signal at 15:05:51 (last 9s of candle), order at 15:05:52, price stable

✅ Check: Every entry shows signal timestamp very close to order timestamp

### Test 2: Stop-Loss Placement

**Before:** Order placed, SL never appears in open orders
**After:** Order placed, SL verified in `state_debug.log`

```
SL order placed: 12345 @ 3220.50
✅ Verified: SL exists in open orders
```

✅ Check: Every entry has corresponding SL verification message

### Test 3: Orphan Order Cleanup

**Before:** Restart → multiple positions, duplicate orders
**After:** Restart → reconciliation cleans up orphans

```
=== STATE RECONCILIATION START ===
ORPHAN ORDERS DETECTED: 2 orders with no position
Cancelled orphan order: 11111 (age: 320s)
```

✅ Check: Restart doesn't create duplicate positions

### Test 4: Position Recovery

**Before:** Crash → position lost, bot doesn't know about it
**After:** Crash → automatic recovery on restart

```
⚠️ DESYNC DETECTED: Exchange has position we don't know about!
RECOVERY: Recovering position 0.1538 @ 3250.50
```

✅ Check: After crash/restart, position is recovered

---

## Configuration

New settings in `unified_trading_bot_v2.py`:

```python
# Timing
CANDLE_CLOSE_THRESHOLD = 0.95      # 95% through candle (last 9s of 3m)
RECONCILE_INTERVAL_SEC = 30        # Check state every 30s
MAX_ORPHAN_ORDER_AGE_SEC = 300     # Cancel orphans older than 5min
```

Adjust if needed:
- Lower `CANDLE_CLOSE_THRESHOLD` for earlier signals (more risk of timing issues)
- Lower `RECONCILE_INTERVAL_SEC` for more frequent checks (more API calls)
- Lower `MAX_ORPHAN_ORDER_AGE_SEC` to clean up faster

---

## What to Watch For

### First Few Days

1. **Check `state_debug.log` for:**
   - Reconciliation warnings
   - Orphan order cleanups
   - Missing stop-loss alerts
   - Position recovery messages

2. **Verify every trade has:**
   - Entry log
   - SL placement confirmation
   - SL verification message
   - Exit log (when closed)

3. **After restart:**
   - Check reconciliation runs
   - Verify no duplicate positions
   - Confirm orphan orders are cleaned

### Red Flags

🚩 **"Position has NO STOP-LOSS"** → Check exchange manually, verify SL exists
🚩 **Repeated orphan order cleanups** → Something is creating orders without tracking them
🚩 **Position recovery on every restart** → State isn't being cleared properly on exit

---

## Emergency Procedures

### If Position is Unprotected

```bash
# 1. Check exchange directly
# 2. Place manual stop-loss at Binance testnet UI
# 3. Check state_debug.log for why SL wasn't placed
```

### If Orphan Orders Keep Appearing

```bash
# 1. Stop bot: Ctrl+C
# 2. Manually cancel all orders at Binance
# 3. Wait 1 minute
# 4. Restart bot
# 5. Check reconciliation log
```

### If Bot Thinks It Has Position But Exchange Doesn't

```bash
# Wait for next reconciliation (max 30s)
# It will auto-detect and clear phantom position
# Or restart bot for immediate reconciliation
```

---

## Summary

| Issue | Old Behavior | New Behavior |
|-------|-------------|--------------|
| **Timing** | Signal on candle open | Signal on candle close (95%) |
| **Stop-Loss** | Place and hope | Place → Verify → Alert if missing |
| **Orphan Orders** | Accumulate forever | Auto-cleanup every 30s |
| **Position Desync** | Cause duplicate trades | Auto-reconcile, recover or clear |
| **Debugging** | Console only | Detailed state log |

---

## Next Steps

1. ✅ **Start bot with v2** - Already configured in `agent.py`
2. ✅ **Monitor both logs** - `trade_log.txt` + `state_debug.log`
3. ✅ **Check first few trades** - Verify SL verification messages
4. ✅ **Test restart** - Confirm no orphan orders appear
5. ✅ **Report any issues** - I'll fix them immediately

The v2 bot is **much more robust** and should eliminate the timing/state/orphan order bugs you experienced.

Let me know if you see any of the old issues again! 🛡️
