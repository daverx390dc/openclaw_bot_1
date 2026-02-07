# unified_trading_bot_v2.py
# FIXED VERSION - Addresses timing, order state, and orphan order issues
import asyncio
import ccxt.pro as ccxtpro
import pandas as pd
import numpy as np
import talib
from datetime import datetime, timezone, timedelta
import os
import time
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.api_keys import API_KEY, API_SECRET

# ════════════════════════════════════════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════════════════════════════════════════

SYMBOL = 'ETH/USDT:USDT'
TIMEFRAME = '3m'
POSITION_SIZE_USDT = 500
LEVERAGE = 10

INITIAL_SL_MULT = 1.1
BREAKEVEN_TRIGGER_R = 1.0
TRAIL_ACTIVATE_AT_R = 1.5
TRAIL_DISTANCE_MULT = 1.8

MIN_CANDLES_FOR_IND = 100
HISTORY_DAYS = 3

TRADE_LOG_FILE = 'logs/trades/trade_log.txt'
STATE_LOG_FILE = 'logs/state_debug.log'

# NEW: Timing and safety configs
CANDLE_CLOSE_THRESHOLD = 0.95  # Only act when 95% through candle duration
RECONCILE_INTERVAL_SEC = 30    # Check exchange state every 30s
MAX_ORPHAN_ORDER_AGE_SEC = 300 # Cancel orphan orders older than 5 minutes

# ════════════════════════════════════════════════════════════════════════════
# GLOBALS
# ════════════════════════════════════════════════════════════════════════════
current_position = None
exchange = None
stop_order_id = None
price_df = pd.DataFrame()
last_processed_candle_time = None  # NEW: Track last processed candle
last_reconcile_time = 0            # NEW: Track last state check


# ════════════════════════════════════════════════════════════════════════════
# LOGGING
# ════════════════════════════════════════════════════════════════════════════
def log_state(message):
    """Debug log for state tracking"""
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    line = f"[{timestamp}] {message}\n"
    print(f"[STATE] {message}")
    try:
        os.makedirs(os.path.dirname(STATE_LOG_FILE), exist_ok=True)
        with open(STATE_LOG_FILE, 'a') as f:
            f.write(line)
    except:
        pass


def log_trade(entry_side, entry_price, exit_price, quantity, reason=""):
    """Append trade result to trade_log.txt"""
    if entry_price is None or exit_price is None:
        pnl_usdt = pnl_pct = 0.0
    else:
        direction = 1 if entry_side.upper() == 'BUY' else -1
        pnl_usdt = direction * (exit_price - entry_price) * quantity
        notional = entry_price * quantity
        pnl_pct = (pnl_usdt / notional) * 100 if notional != 0 else 0.0

    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    entry_str = f"{entry_price:.2f}" if entry_price is not None else "N/A"
    exit_str = f"{exit_price:.2f}" if exit_price is not None else "N/A"
    line = (
        f"{timestamp} | "
        f"Side: {entry_side} | "
        f"Entry: {entry_str} | "
        f"Exit: {exit_str} | "
        f"Qty: {quantity:.4f} | "
        f"PNL: {pnl_usdt:+.2f} USDT ({pnl_pct:+.2f}%) | "
        f"Reason: {reason}\n"
    )
    print(line.strip())
    with open(TRADE_LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line)


# ════════════════════════════════════════════════════════════════════════════
# INDICATOR CALCULATION
# ════════════════════════════════════════════════════════════════════════════
def compute_indicators(df):
    """Calculate RSI, Bollinger Bands, ATR, Volume SMA"""
    if len(df) < MIN_CANDLES_FOR_IND:
        return
    close = df['close'].to_numpy(dtype=np.float64)
    high = df['high'].to_numpy(dtype=np.float64)
    low = df['low'].to_numpy(dtype=np.float64)
    volume = df['volume'].to_numpy(dtype=np.float64)

    df['rsi'] = talib.RSI(close, timeperiod=14)
    upper, middle, lower = talib.BBANDS(close, timeperiod=20, nbdevup=2, nbdevdn=2)
    df['bb_upper'] = upper
    df['bb_middle'] = middle
    df['bb_lower'] = lower
    df['atr'] = talib.ATR(high, low, close, timeperiod=14)
    df['volume_sma'] = talib.SMA(volume, timeperiod=20)


# ════════════════════════════════════════════════════════════════════════════
# SIGNAL DETECTION
# ════════════════════════════════════════════════════════════════════════════
def detect_signal(df):
    """Detect BUY/SELL signals - ONLY on completed candles"""
    if len(df) < 2:
        return None

    if pd.isna(df['rsi'].iloc[-1]) or pd.isna(df['bb_middle'].iloc[-1]):
        return None

    i = -1
    prev = -2

    # BUY SIGNAL
    rsi_buy = (df['rsi'].iloc[i] > 50) and \
              (df['rsi'].iloc[i] > df['rsi'].iloc[prev]) and \
              (df['rsi'].iloc[prev] >= 40)
    bb_buy = (df['close'].iloc[i] > df['bb_middle'].iloc[i]) and \
             (df['close'].iloc[i] > df['bb_upper'].iloc[prev] or
              (df['bb_upper'].iloc[i] - df['bb_lower'].iloc[i]) >
              (df['bb_upper'].iloc[prev] - df['bb_lower'].iloc[prev]))
    volume_buy = df['volume'].iloc[i] > df['volume_sma'].iloc[i] * 1.5

    if rsi_buy and bb_buy and volume_buy:
        price = df['close'].iloc[i]
        atr_val = df['atr'].iloc[i]
        risk_pct = 1.1 * atr_val / price
        sl = price * (1 - risk_pct)
        tp = price * (1 + 3 * risk_pct)
        print(f"  🚀 BUY SIGNAL @ {price:,.2f} | {df['timestamp'].iloc[i]}")
        print(f"     RSI {df['rsi'].iloc[i]:.1f} | ATR {atr_val:.2f}")
        print(f"     Suggested SL ≈ {sl:,.2f} | TP(1:3) ≈ {tp:,.2f}")
        log_state(f"BUY signal detected: price={price:.2f}, RSI={df['rsi'].iloc[i]:.1f}")
        return 'BUY'

    # SELL SIGNAL
    rsi_sell = (df['rsi'].iloc[i] < 50) and \
               (df['rsi'].iloc[i] < df['rsi'].iloc[prev]) and \
               (df['rsi'].iloc[prev] <= 60)
    bb_sell = (df['close'].iloc[i] < df['bb_middle'].iloc[i]) and \
              (df['close'].iloc[i] < df['bb_lower'].iloc[prev] or
               (df['bb_upper'].iloc[i] - df['bb_lower'].iloc[i]) >
               (df['bb_upper'].iloc[prev] - df['bb_lower'].iloc[prev]))
    volume_sell = df['volume'].iloc[i] > df['volume_sma'].iloc[i] * 1.5

    if rsi_sell and bb_sell and volume_sell:
        price = df['close'].iloc[i]
        atr_val = df['atr'].iloc[i]
        risk_pct = 1.1 * atr_val / price
        sl = price * (1 + risk_pct)
        tp = price * (1 - 3 * risk_pct)
        print(f"  🔴 SELL SIGNAL @ {price:,.2f} | {df['timestamp'].iloc[i]}")
        print(f"     RSI {df['rsi'].iloc[i]:.1f} | ATR {atr_val:.2f}")
        print(f"     Suggested SL ≈ {sl:,.2f} | TP(1:3) ≈ {tp:,.2f}")
        log_state(f"SELL signal detected: price={price:.2f}, RSI={df['rsi'].iloc[i]:.1f}")
        return 'SELL'

    return None


# ════════════════════════════════════════════════════════════════════════════
# EXCHANGE INITIALIZATION
# ════════════════════════════════════════════════════════════════════════════
async def init_exchange():
    global exchange, SYMBOL
    exchange = ccxtpro.binanceusdm({
        'apiKey': API_KEY,
        'secret': API_SECRET,
        'enableRateLimit': True,
        'options': {'defaultType': 'future', 'adjustForTimeDifference': True},
    })
    exchange.enableDemoTrading(True)
    print("Loading markets...")
    await exchange.load_markets(reload=True)

    detected = next((m for m in exchange.markets if 'ETH' in m and 'USDT' in m), None)
    if detected and detected != SYMBOL:
        print(f"Symbol updated: {SYMBOL} → {detected}")
        SYMBOL = detected
    if not detected:
        raise ValueError("No ETH/USDT market found")
    print(f"Using symbol: {SYMBOL}")

    try:
        await exchange.set_position_mode(hedged=False, symbol=SYMBOL)
        print("Position mode: one-way")
    except Exception as e:
        print(f"Position mode failed (non-fatal): {e}")

    try:
        await exchange.set_leverage(LEVERAGE, SYMBOL)
        print(f"Leverage set to {LEVERAGE}x")
    except Exception as e:
        print(f"Leverage failed (non-fatal): {e}")

    return exchange


# ════════════════════════════════════════════════════════════════════════════
# HISTORICAL DATA
# ════════════════════════════════════════════════════════════════════════════
async def load_historical_data():
    """Load recent historical data for initial indicators"""
    try:
        since = int((datetime.now(timezone.utc) - timedelta(days=HISTORY_DAYS)).timestamp() * 1000)
        print(f"Fetching historical data since {datetime.fromtimestamp(since/1000, timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC...")
        ohlcv = []
        temp_since = since
        while temp_since < int(time.time() * 1000):
            data = await exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, since=temp_since, limit=1000)
            if not data:
                break
            ohlcv.extend(data)
            temp_since = data[-1][0] + 1
            await asyncio.sleep(0.4)

        if not ohlcv:
            print("No historical data fetched.")
            return pd.DataFrame()

        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df.drop_duplicates(subset='timestamp', keep='last').reset_index(drop=True)
        print(f"Loaded {len(df)} historical candles.")
        return df
    except Exception as e:
        print(f"Historical data error: {e}")
        return pd.DataFrame()


# ════════════════════════════════════════════════════════════════════════════
# NEW: STATE RECONCILIATION
# ════════════════════════════════════════════════════════════════════════════
async def reconcile_state():
    """
    Cross-check internal state with exchange reality
    Fixes: orphan orders, position desync, missing stop-loss
    """
    global current_position, stop_order_id
    
    log_state("=== STATE RECONCILIATION START ===")
    
    try:
        # 1. Get actual position from exchange
        positions = await exchange.fetch_positions([SYMBOL])
        exchange_position = next((p for p in positions if float(p.get('positionAmt', 0)) != 0), None)
        
        # 2. Get all open orders
        open_orders = await exchange.fetch_open_orders(SYMBOL)
        
        log_state(f"Exchange position: {exchange_position['positionAmt'] if exchange_position else 'None'}")
        log_state(f"Internal position: {current_position['side'] if current_position else 'None'}")
        log_state(f"Open orders: {len(open_orders)}")
        
        # 3. CASE 1: Exchange has position, we don't know about it
        if exchange_position and not current_position:
            amt = float(exchange_position['positionAmt'])
            entry_price = float(exchange_position.get('entryPrice', 0))
            
            print(f"⚠️ DESYNC DETECTED: Exchange has position we don't know about!")
            log_state(f"RECOVERY: Recovering position {amt} @ {entry_price}")
            
            current_position = {
                'side': 'long' if amt > 0 else 'short',
                'entry_price': entry_price,
                'quantity': abs(amt),
                'initial_risk': 0.0,  # Unknown, will recalculate
                'sl_price': 0.0,
                'breakeven_triggered': False,
                'trailing_active': False,
                'trail_distance': 0.0,
            }
            
            # Check if there's a stop order
            stop_orders = [o for o in open_orders if 'STOP' in o['type'].upper()]
            if stop_orders:
                stop_order_id = stop_orders[0]['id']
                current_position['sl_price'] = float(stop_orders[0].get('stopPrice', 0))
                log_state(f"Found existing SL order: {stop_order_id} @ {current_position['sl_price']}")
            else:
                log_state("WARNING: Position has no stop-loss! Will place one.")
        
        # 4. CASE 2: We think we have position, but exchange doesn't
        elif current_position and not exchange_position:
            print(f"⚠️ DESYNC: We think we have {current_position['side']} but exchange shows none")
            log_state(f"RECOVERY: Clearing phantom position")
            current_position = None
            stop_order_id = None
        
        # 5. CASE 3: Orphan orders (orders exist but no position)
        if not exchange_position and len(open_orders) > 0:
            print(f"⚠️ ORPHAN ORDERS DETECTED: {len(open_orders)} orders with no position")
            log_state(f"CLEANUP: Cancelling {len(open_orders)} orphan orders")
            
            for order in open_orders:
                try:
                    # Check order age before cancelling
                    order_time = order.get('timestamp', 0) / 1000  # Convert to seconds
                    age = time.time() - order_time
                    
                    if age > MAX_ORPHAN_ORDER_AGE_SEC:
                        await exchange.cancel_order(order['id'], SYMBOL)
                        log_state(f"Cancelled orphan order: {order['id']} (age: {age:.0f}s)")
                    else:
                        log_state(f"Keeping recent order: {order['id']} (age: {age:.0f}s)")
                except Exception as e:
                    log_state(f"Failed to cancel {order['id']}: {e}")
        
        # 6. CASE 4: Position exists but no stop-loss order
        if current_position and exchange_position:
            stop_orders = [o for o in open_orders if 'STOP' in o['type'].upper()]
            if len(stop_orders) == 0:
                print(f"⚠️ CRITICAL: Position has NO STOP-LOSS!")
                log_state("RECOVERY: Position exists but no SL - will place emergency SL")
                # Will be handled by next update cycle
            elif len(stop_orders) > 1:
                print(f"⚠️ WARNING: Multiple stop orders ({len(stop_orders)}) - cancelling extras")
                # Keep only the first one
                for order in stop_orders[1:]:
                    try:
                        await exchange.cancel_order(order['id'], SYMBOL)
                        log_state(f"Cancelled duplicate SL: {order['id']}")
                    except:
                        pass
        
        log_state("=== STATE RECONCILIATION COMPLETE ===")
        
    except Exception as e:
        log_state(f"Reconciliation error: {e}")
        print(f"❌ State reconciliation failed: {e}")


# ════════════════════════════════════════════════════════════════════════════
# ORDER MANAGEMENT (IMPROVED)
# ════════════════════════════════════════════════════════════════════════════
async def cancel_all_orders():
    """Cancel ALL open orders with retry and verification"""
    try:
        for attempt in range(3):
            orders = await exchange.fetch_open_orders(SYMBOL)
            if len(orders) == 0:
                return True
            
            log_state(f"Cancelling {len(orders)} orders (attempt {attempt+1})")
            
            for order in orders:
                try:
                    await exchange.cancel_order(order['id'], SYMBOL)
                    log_state(f"Cancelled: {order['id']} ({order['type']})")
                except Exception as e:
                    log_state(f"Cancel failed for {order['id']}: {e}")
            
            await asyncio.sleep(0.5)
        
        # Final verification
        remaining = await exchange.fetch_open_orders(SYMBOL)
        if len(remaining) > 0:
            log_state(f"WARNING: {len(remaining)} orders remain after 3 attempts")
            return False
        
        return True
    except Exception as e:
        log_state(f"cancel_all_orders error: {e}")
        return False


async def verify_no_position():
    """Verify we have no position on exchange"""
    try:
        positions = await exchange.fetch_positions([SYMBOL])
        active = next((p for p in positions if float(p.get('positionAmt', 0)) != 0), None)
        if active:
            amt = float(active['positionAmt'])
            log_state(f"Position check: FOUND {amt}")
            return False
        log_state("Position check: CLEAR")
        return True
    except Exception as e:
        log_state(f"Position check error: {e}")
        return True


def get_atr_from_df(df):
    """Get ATR from dataframe"""
    if len(df) < 30 or 'atr' not in df.columns:
        return None
    atr = df['atr'].iloc[-1]
    return None if pd.isna(atr) else float(atr)


# ════════════════════════════════════════════════════════════════════════════
# POSITION ENTRY (IMPROVED)
# ════════════════════════════════════════════════════════════════════════════
async def place_entry(side: str, signal_price: float, atr: float):
    global current_position, stop_order_id
    
    log_state(f"=== ENTRY ATTEMPT: {side} @ {signal_price:.2f} ===")
    
    # SAFETY CHECK 1: Verify no existing position
    has_no_position = await verify_no_position()
    if not has_no_position:
        print(f"❌ ENTRY BLOCKED: Exchange shows active position!")
        log_state("ENTRY BLOCKED: Position already exists")
        return
    
    # SAFETY CHECK 2: Cancel any orphan orders first
    await cancel_all_orders()
    await asyncio.sleep(0.5)
    
    risk_dist = INITIAL_SL_MULT * atr
    qty_raw = (POSITION_SIZE_USDT / signal_price) * LEVERAGE
    qty = exchange.amount_to_precision(SYMBOL, qty_raw)

    print(f"ENTRY → {side} | Price: {signal_price:.2f} | ATR: {atr:.2f} | Qty: {qty}")
    log_state(f"Entry params: side={side}, qty={qty}, risk_dist={risk_dist:.2f}")
    
    side_str = 'buy' if side == 'BUY' else 'sell'

    try:
        # Place market order
        order = await exchange.create_market_order(SYMBOL, side_str, qty)
        print(f"✅ ENTRY FILLED: {order.get('id')}")
        log_state(f"Entry order filled: {order}")
        
        entry_price = float(order.get('average') or order.get('price') or signal_price)
        notional = entry_price * float(qty)

        sl_price = entry_price - risk_dist if side == 'BUY' else entry_price + risk_dist

        current_position = {
            'side': 'long' if side == 'BUY' else 'short',
            'entry_price': entry_price,
            'quantity': float(qty),
            'initial_risk': risk_dist,
            'sl_price': sl_price,
            'breakeven_triggered': False,
            'trailing_active': False,
            'trail_distance': 0.0,
            'entry_notional': notional,
            'entry_time': datetime.now(timezone.utc),
        }
        
        log_state(f"Position created: {current_position}")

        # Place stop-loss with verification
        sl_side = 'sell' if side == 'BUY' else 'buy'
        
        try:
            sl_order = await exchange.create_order(
                SYMBOL, 'STOP_MARKET', sl_side, qty, None,
                {'stopPrice': sl_price, 'reduceOnly': True, 'workingType': 'MARK_PRICE'}
            )
            stop_order_id = sl_order['id']
            print(f"✅ Initial SL placed @ {sl_price:.2f} (ID: {stop_order_id})")
            log_state(f"SL order placed: {stop_order_id} @ {sl_price:.2f}")
            
            # VERIFY the stop order was actually placed
            await asyncio.sleep(0.5)
            orders = await exchange.fetch_open_orders(SYMBOL)
            sl_exists = any(o['id'] == stop_order_id for o in orders)
            if not sl_exists:
                log_state(f"WARNING: SL order {stop_order_id} not found in open orders!")
                print(f"⚠️ WARNING: Stop-loss order may not be active!")
            
        except Exception as e:
            log_state(f"CRITICAL: SL placement failed: {e}")
            print(f"❌ CRITICAL: Failed to place stop-loss! {e}")
            print(f"⚠️ Position is UNPROTECTED - manual intervention required!")

        # Log entry
        log_trade(side, entry_price, None, float(qty), "ENTRY")

    except Exception as e:
        log_state(f"Entry failed: {e}")
        print(f"❌ Entry failed: {type(e).__name__} → {e}")


# ════════════════════════════════════════════════════════════════════════════
# TRAILING STOP-LOSS (IMPROVED)
# ════════════════════════════════════════════════════════════════════════════
async def update_trailing_or_close(price, atr):
    global current_position, stop_order_id
    if not current_position:
        return

    entry = current_position['entry_price']
    side = current_position['side']
    risk = current_position['initial_risk']
    qty = current_position['quantity']

    r_profit = (price - entry) / risk if side == 'long' else (entry - price) / risk
    updated = False

    # Breakeven
    if not current_position['breakeven_triggered'] and r_profit >= BREAKEVEN_TRIGGER_R:
        current_position['sl_price'] = entry
        current_position['breakeven_triggered'] = True
        print(f"✅ Breakeven triggered @ +{r_profit:.2f}R → SL @ {entry:.2f}")
        log_state(f"Breakeven: SL moved to {entry:.2f}")
        updated = True

    # Trailing activation
    if r_profit >= TRAIL_ACTIVATE_AT_R and not current_position['trailing_active']:
        current_position['trailing_active'] = True
        current_position['trail_distance'] = TRAIL_DISTANCE_MULT * atr
        print(f"✅ Trailing activated @ +{r_profit:.2f}R | distance {current_position['trail_distance']:.2f}")
        log_state(f"Trailing activated: distance={current_position['trail_distance']:.2f}")
        updated = True

    # Trailing update
    if current_position['trailing_active']:
        if side == 'long':
            new_sl = price - current_position['trail_distance']
            if new_sl > current_position['sl_price'] + 0.3 * atr:
                current_position['sl_price'] = new_sl
                print(f"📈 Trailing SL moved to {new_sl:.2f}")
                log_state(f"Trailing update: SL={new_sl:.2f}")
                updated = True
        else:
            new_sl = price + current_position['trail_distance']
            if new_sl < current_position['sl_price'] - 0.3 * atr:
                current_position['sl_price'] = new_sl
                print(f"📉 Trailing SL moved to {new_sl:.2f}")
                log_state(f"Trailing update: SL={new_sl:.2f}")
                updated = True

    # Update SL order only if changed
    if updated:
        success = await cancel_all_orders()
        if not success:
            log_state("SL update skipped - cancel failed")
            print("⚠️ Skipping SL update - cancellation failed")
            return
        
        stop_order_id = None
        sl_side = 'sell' if side == 'long' else 'buy'
        
        try:
            new_sl_order = await exchange.create_order(
                SYMBOL, 'STOP_MARKET', sl_side, qty, None,
                {'stopPrice': current_position['sl_price'], 'reduceOnly': True}
            )
            stop_order_id = new_sl_order['id']
            print(f"✅ SL order updated @ {current_position['sl_price']:.2f}")
            log_state(f"SL order updated: {stop_order_id} @ {current_position['sl_price']:.2f}")
            
            # VERIFY
            await asyncio.sleep(0.3)
            orders = await exchange.fetch_open_orders(SYMBOL)
            sl_exists = any(o['id'] == stop_order_id for o in orders)
            if not sl_exists:
                log_state(f"WARNING: Updated SL {stop_order_id} not in open orders!")
            
        except Exception as e:
            log_state(f"SL update failed: {e}")
            print(f"❌ SL update failed: {e}")


# ════════════════════════════════════════════════════════════════════════════
# POSITION CLOSE
# ════════════════════════════════════════════════════════════════════════════
async def close_position(price=None, reason="Manual/SL/TP"):
    global current_position, stop_order_id
    if not current_position:
        return

    side = current_position['side']
    qty = current_position['quantity']
    entry_price = current_position['entry_price']
    
    log_state(f"=== CLOSING POSITION: {reason} ===")

    try:
        side_str = 'sell' if side == 'long' else 'buy'
        close_order = await exchange.create_market_order(
            SYMBOL, side_str, qty, params={'reduceOnly': True}
        )
        print(f"✅ CLOSED {reason} | {qty:.4f} @ ~{price or 'market'}")
        log_state(f"Position closed: {close_order}")
        
        close_price = price or float(close_order.get('average') or close_order.get('price') or entry_price)
        log_trade('BUY' if side == 'long' else 'SELL', entry_price, close_price, qty, reason)
        
    except Exception as e:
        log_state(f"Close failed: {e}")
        print(f"❌ Close failed: {e}")

    await cancel_all_orders()
    current_position = None
    stop_order_id = None
    log_state("Position state cleared")


# ════════════════════════════════════════════════════════════════════════════
# NEW: Candle timing helper
# ════════════════════════════════════════════════════════════════════════════
def is_candle_closed(candle_timestamp, timeframe='3m'):
    """
    Check if a candle is truly closed (not just updating)
    Returns True only when we're past the candle close time
    """
    # Convert timeframe to seconds
    tf_seconds = {'1m': 60, '3m': 180, '5m': 300, '15m': 900, '1h': 3600}[timeframe]
    
    candle_time = candle_timestamp.timestamp() if isinstance(candle_timestamp, datetime) else candle_timestamp / 1000
    current_time = time.time()
    
    # Time since candle started
    time_in_candle = current_time - candle_time
    
    # Only consider it closed if we're past the threshold
    progress = time_in_candle / tf_seconds
    
    return progress >= CANDLE_CLOSE_THRESHOLD


# ════════════════════════════════════════════════════════════════════════════
# MAIN LOOP (IMPROVED)
# ════════════════════════════════════════════════════════════════════════════
async def main_loop():
    global exchange, current_position, price_df, last_processed_candle_time, last_reconcile_time

    exchange = await init_exchange()
    price_df = await load_historical_data()
    
    if not price_df.empty:
        compute_indicators(price_df)
        print(f"Initial indicators computed on {len(price_df)} candles")

    # Initial state reconciliation
    await reconcile_state()

    print(f"  {'═'*60}")
    print(f"UNIFIED TRADING BOT V2 STARTED (FIXED)")
    print(f"Symbol: {SYMBOL} | Timeframe: {TIMEFRAME} | Leverage: {LEVERAGE}x")
    print(f"Strategy: RSI + Bollinger Bands + Volume")
    print(f"Fixes: Timing, State Sync, Orphan Orders")
    print(f"Press Ctrl+C to stop")
    print(f"{'═'*60}\n")

    if not os.path.exists(TRADE_LOG_FILE):
        os.makedirs(os.path.dirname(TRADE_LOG_FILE), exist_ok=True)
        with open(TRADE_LOG_FILE, 'w', encoding='utf-8') as f:
            f.write("Timestamp | Side | Entry | Exit | Qty | PNL USDT | PNL % | Reason\n")

    # Initial cleanup
    print("🧹 Initial cleanup...")
    await cancel_all_orders()
    await asyncio.sleep(1)

    while True:
        try:
            # Periodic state reconciliation
            current_time = time.time()
            if current_time - last_reconcile_time >= RECONCILE_INTERVAL_SEC:
                await reconcile_state()
                last_reconcile_time = current_time

            # Watch OHLCV via WebSocket
            ohlcv_list = await exchange.watch_ohlcv(SYMBOL, TIMEFRAME)
            candle = ohlcv_list[-1]
            ts_ms = candle[0]
            ts_dt = pd.to_datetime(ts_ms, unit='ms')

            # Update or append candle
            if not price_df.empty and price_df['timestamp'].iloc[-1] == ts_dt:
                # Updating existing candle
                price_df.loc[price_df.index[-1], ['open','high','low','close','volume']] = candle[1:6]
            else:
                # New candle
                new_row = {
                    'timestamp': ts_dt,
                    'open': float(candle[1]),
                    'high': float(candle[2]),
                    'low': float(candle[3]),
                    'close': float(candle[4]),
                    'volume': float(candle[5]),
                }
                price_df = pd.concat([price_df, pd.DataFrame([new_row])], ignore_index=True)

                if len(price_df) > 500:
                    price_df = price_df.iloc[-500:].reset_index(drop=True)

            # Compute indicators
            compute_indicators(price_df)
            price = float(candle[4])
            atr = get_atr_from_df(price_df)

            # Manage existing position
            if current_position and atr:
                await update_trailing_or_close(price, atr)
                direction = "Long" if current_position['side'] == 'long' else "Short"
                
                if current_position['side'] == 'long':
                    pnl_raw = (price - current_position['entry_price']) * current_position['quantity']
                else:
                    pnl_raw = (current_position['entry_price'] - price) * current_position['quantity']
                
                pnl_sign = "+" if pnl_raw >= 0 else ""
                print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {direction} @ {current_position['entry_price']:.2f} | "
                      f"Price: {price:.2f} | PNL: {pnl_sign}{pnl_raw:.2f} | SL: {current_position['sl_price']:.2f}")

            # NEW: Only check for signals on CLOSED candles
            if ts_dt != last_processed_candle_time:
                # Check if candle is truly closed
                if is_candle_closed(ts_dt, TIMEFRAME):
                    last_processed_candle_time = ts_dt
                    
                    if not current_position and len(price_df) >= MIN_CANDLES_FOR_IND:
                        signal = detect_signal(price_df)

                        if signal in ['BUY', 'SELL'] and atr:
                            # Extra verification before entry
                            has_no_position = await verify_no_position()
                            if not has_no_position:
                                log_state(f"Signal {signal} BLOCKED - position exists")
                                print(f"⚠️ Signal {signal} BLOCKED - exchange shows active position!")
                                continue

                            # Check balance
                            balance = await exchange.fetch_balance()
                            usdt_free = balance.get('USDT', {}).get('free', 0)
                            if usdt_free >= POSITION_SIZE_USDT * 1.1:
                                print(f"  {'─'*60}")
                                await place_entry(signal, price, atr)
                                print(f"{'─'*60}\n")
                            else:
                                log_state(f"Signal {signal} skipped - low balance: ${usdt_free:.2f}")
                                print(f"⚠️ Signal {signal} ignored - insufficient balance (${usdt_free:.2f})")

            await asyncio.sleep(0.1)

        except KeyboardInterrupt:
            print("  Stopped by user.")
            break
        except Exception as e:
            log_state(f"Loop error: {e}")
            print(f"❌ Loop error: {type(e).__name__} → {str(e)}")
            await asyncio.sleep(5)

    # Cleanup
    if current_position:
        await close_position(reason="Script stopped")
    await exchange.close()
    print("Bot shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main_loop())
