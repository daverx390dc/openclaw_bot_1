# unified_trading_bot_v3.py
# FIXED VERSION - Critical fixes for race conditions, SL orders, and state management
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
POSITION_SIZE_USDT = 50
LEVERAGE = 30

INITIAL_SL_MULT = 1.1
BREAKEVEN_TRIGGER_R = 1.0
TRAIL_ACTIVATE_AT_R = 1.5
TRAIL_DISTANCE_MULT = 1.8

MIN_CANDLES_FOR_IND = 100
HISTORY_DAYS = 3

TRADE_LOG_FILE = 'logs/trades/trade_log.txt'
STATE_LOG_FILE = 'logs/state_debug.log'

# Timing and safety configs
CANDLE_CLOSE_THRESHOLD = 0.95
RECONCILE_INTERVAL_SEC = 30
MAX_ORPHAN_ORDER_AGE_SEC = 300

# NEW: Locking and SL verification
SL_VERIFICATION_WAIT = 2.0  # Wait 2 seconds before verifying SL
SL_RETRY_ATTEMPTS = 3       # Retry SL placement if verification fails

# ════════════════════════════════════════════════════════════════════════════
# GLOBALS
# ════════════════════════════════════════════════════════════════════════════
current_position = None
exchange = None
stop_order_id = None
price_df = pd.DataFrame()
last_processed_candle_time = None
last_reconcile_time = 0

# NEW: Lock to prevent concurrent entry processing
entry_lock = asyncio.Lock()
processing_signal = False

# ════════════════════════════════════════════════════════════════════════════
# LOGGING
# ════════════════════════════════════════════════════════════════════════════
def log_state(msg):
    """Log state changes for debugging"""
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    log_dir = os.path.dirname(STATE_LOG_FILE)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    with open(STATE_LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] {msg}\n")

def log_trade(side, entry, exit_price, qty, pnl, pnl_pct, reason):
    """Log completed trades"""
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    with open(TRADE_LOG_FILE, 'a', encoding='utf-8') as f:
        pnl_sign = "+" if pnl >= 0 else ""
        f.write(f"{timestamp} | Side: {side} | Entry: {entry:.2f} | Exit: {exit_price or 'N/A'} | "
                f"Qty: {qty:.4f} | PNL: {pnl_sign}{pnl:.2f} USDT ({pnl_sign}{pnl_pct:.2f}%) | Reason: {reason}\n")
    print(f"  {timestamp} | Side: {side} | Entry: {entry:.2f} | Exit: {exit_price or 'N/A'} | "
          f"Qty: {qty:.4f} | PNL: {pnl_sign}{pnl:.2f} USDT ({pnl_sign}{pnl_pct:.2f}%) | Reason: {reason}")

# ════════════════════════════════════════════════════════════════════════════
# EXCHANGE INIT
# ════════════════════════════════════════════════════════════════════════════
async def init_exchange():
    ex = ccxtpro.binanceusdm({
        'apiKey': API_KEY,
        'secret': API_SECRET,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'future'
        }
    })
    
    # Enable demo trading - switches to https://demo-fapi.binance.com
    ex.enable_demo_trading(True)
    
    print("Loading markets...")
    await ex.load_markets()
    print(f"Using symbol: {SYMBOL}")
    print(f"Demo API endpoint: {ex.urls.get('api', {}).get('fapiPrivate', 'N/A')}")
    
    try:
        await ex.set_position_mode(True, SYMBOL)
    except Exception as e:
        print(f"Position mode failed (non-fatal): {e}")
    
    try:
        await ex.set_leverage(LEVERAGE, SYMBOL)
        print(f"Leverage set to {LEVERAGE}x")
    except Exception as e:
        print(f"Leverage set failed: {e}")
    
    return ex

# ════════════════════════════════════════════════════════════════════════════
# DATA LOADING
# ════════════════════════════════════════════════════════════════════════════
async def load_historical_data():
    since = int((datetime.utcnow() - timedelta(days=HISTORY_DAYS)).timestamp() * 1000)
    print(f"Fetching historical data since {datetime.utcfromtimestamp(since/1000)} UTC...")
    
    ohlcv = await exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, since=since, limit=1500)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    print(f"Loaded {len(df)} historical candles.")
    return df

# ════════════════════════════════════════════════════════════════════════════
# INDICATORS
# ════════════════════════════════════════════════════════════════════════════
def compute_indicators(df):
    if len(df) < 50:
        return
    
    df['rsi'] = talib.RSI(df['close'].values, timeperiod=14)
    df['bb_upper'], df['bb_middle'], df['bb_lower'] = talib.BBANDS(
        df['close'].values, timeperiod=20, nbdevup=2, nbdevdn=2)
    df['atr'] = talib.ATR(df['high'].values, df['low'].values, df['close'].values, timeperiod=14)
    df['volume_sma'] = talib.SMA(df['volume'].values, timeperiod=20)

def get_atr_from_df(df):
    if len(df) < 14 or 'atr' not in df.columns:
        return None
    atr = df['atr'].iloc[-1]
    return atr if not np.isnan(atr) else None

# ════════════════════════════════════════════════════════════════════════════
# SIGNAL DETECTION
# ════════════════════════════════════════════════════════════════════════════
def detect_signal(df):
    if len(df) < MIN_CANDLES_FOR_IND:
        return None
    
    for i in [len(df)-2]:
        row = df.iloc[i]
        prev = df.iloc[i-1] if i > 0 else None
        
        if pd.isna(row['rsi']) or pd.isna(row['bb_lower']):
            continue
        
        price = row['close']
        rsi = row['rsi']
        bb_lower = row['bb_lower']
        bb_upper = row['bb_upper']
        vol = row['volume']
        vol_sma = row['volume_sma']
        
        # BUY signal
        if (rsi > 30 and rsi < 55 and 
            price <= bb_lower * 1.005 and 
            vol > vol_sma * 1.5 and 
            prev is not None and prev['rsi'] <= 30):
            
            log_state(f"BUY signal detected: price={price:.2f}, RSI={df['rsi'].iloc[i]:.1f}")
            
            atr = get_atr_from_df(df)
            if atr:
                suggested_sl = price - (atr * INITIAL_SL_MULT)
                tp_3r = price + (atr * INITIAL_SL_MULT * 3)
                print(f"🚀 BUY SIGNAL @ {price:,.2f} | {df['timestamp'].iloc[i]}")
                print(f"   RSI {rsi:.1f} | ATR {atr:.2f}")
                print(f"   Suggested SL ≈ {suggested_sl:,.2f} | TP(1:3) ≈ {tp_3r:,.2f}")
            
            return 'BUY'
        
        # SELL signal
        if (rsi < 70 and rsi > 45 and 
            price >= bb_upper * 0.995 and 
            vol > vol_sma * 1.5 and 
            prev is not None and prev['rsi'] >= 70):
            
            log_state(f"SELL signal detected: price={price:.2f}, RSI={df['rsi'].iloc[i]:.1f}")
            
            atr = get_atr_from_df(df)
            if atr:
                suggested_sl = price + (atr * INITIAL_SL_MULT)
                tp_3r = price - (atr * INITIAL_SL_MULT * 3)
                print(f"🔻 SELL SIGNAL @ {price:,.2f} | {df['timestamp'].iloc[i]}")
                print(f"   RSI {rsi:.1f} | ATR {atr:.2f}")
                print(f"   Suggested SL ≈ {suggested_sl:,.2f} | TP(1:3) ≈ {tp_3r:,.2f}")
            
            return 'SELL'
    
    return None

# ════════════════════════════════════════════════════════════════════════════
# STATE MANAGEMENT (IMPROVED)
# ════════════════════════════════════════════════════════════════════════════
async def verify_no_position():
    """Double-check no position exists on exchange"""
    try:
        positions = await exchange.fetch_positions([SYMBOL])
        for pos in positions:
            if pos['contracts'] and abs(pos['contracts']) > 0:
                return False
        return True
    except Exception as e:
        log_state(f"Position verification failed: {e}")
        return False

async def reconcile_state():
    """Sync internal state with exchange"""
    global current_position, stop_order_id
    
    log_state("=== STATE RECONCILIATION START ===")
    
    try:
        # Get exchange position
        positions = await exchange.fetch_positions([SYMBOL])
        exchange_position = None
        for pos in positions:
            if pos['contracts'] and abs(pos['contracts']) > 0:
                exchange_position = pos
                break
        
        log_state(f"Exchange position: {exchange_position['side'] if exchange_position else 'None'}")
        log_state(f"Internal position: {current_position['side'] if current_position else 'None'}")
        
        # Get open orders
        open_orders = await exchange.fetch_open_orders(SYMBOL)
        log_state(f"Open orders: {len(open_orders)}")
        
        # Reconcile
        if current_position and not exchange_position:
            # We think we have position but exchange doesn't
            log_state("⚠️ DESYNC: We think we have position but exchange shows none")
            log_state("RECOVERY: Clearing phantom position")
            current_position = None
            stop_order_id = None
        
        if exchange_position and not current_position:
            # Exchange has position but we don't track it
            log_state("⚠️ DESYNC: Exchange has position but we don't track it")
            log_state("RECOVERY: Closing untracked position")
            await exchange.close_position(SYMBOL)
        
        # Clean up orphan orders
        current_time = time.time()
        for order in open_orders:
            order_age = current_time - (order['timestamp'] / 1000)
            if order_age > MAX_ORPHAN_ORDER_AGE_SEC:
                log_state(f"Canceling orphan order: {order['id']} (age: {order_age:.0f}s)")
                try:
                    await exchange.cancel_order(order['id'], SYMBOL)
                except:
                    pass
        
        log_state("=== STATE RECONCILIATION COMPLETE ===")
    
    except Exception as e:
        log_state(f"Reconciliation error: {e}")

async def cancel_all_orders():
    """Cancel all open orders for the symbol"""
    try:
        await exchange.cancel_all_orders(SYMBOL)
    except Exception as e:
        log_state(f"Cancel all orders failed: {e}")

# ════════════════════════════════════════════════════════════════════════════
# ENTRY LOGIC (FIXED - WITH LOCK AND BETTER SL)
# ════════════════════════════════════════════════════════════════════════════
async def place_entry(side: str, signal_price: float, atr: float):
    """Place entry order with improved SL handling"""
    global current_position, stop_order_id, processing_signal
    
    # Acquire lock to prevent concurrent entries
    async with entry_lock:
        if processing_signal:
            log_state(f"Entry BLOCKED - already processing a signal")
            print("⚠️ Entry blocked - signal already being processed")
            return
        
        processing_signal = True
        
        try:
            log_state(f"=== ENTRY ATTEMPT: {side} @ {signal_price:.2f} ===")
            
            # Final position check
            log_state("Position check: CLEAR")
            has_no_position = await verify_no_position()
            if not has_no_position:
                log_state("Entry ABORTED - position exists on exchange")
                print("❌ Entry aborted - position already exists!")
                return
            
            # Calculate position size
            qty = (POSITION_SIZE_USDT * LEVERAGE) / signal_price
            qty = round(qty, 4)
            
            risk_distance = atr * INITIAL_SL_MULT
            sl_price = signal_price - risk_distance if side == 'BUY' else signal_price + risk_distance
            
            print(f"ENTRY → {side} | Price: {signal_price:.2f} | ATR: {atr:.2f} | Qty: {qty}")
            log_state(f"Entry params: side={side}, qty={qty}, risk_dist={risk_distance:.2f}")
            
            # Place market entry order
            order = await exchange.create_order(
                symbol=SYMBOL,
                type='market',
                side='buy' if side == 'BUY' else 'sell',
                amount=qty
            )
            
            log_state(f"Entry order filled: {order}")
            print(f"✅ ENTRY FILLED: {order['id']}")
            
            # Create position state
            current_position = {
                'side': 'long' if side == 'BUY' else 'short',
                'entry_price': order['average'],
                'quantity': qty,
                'initial_risk': risk_distance,
                'sl_price': sl_price,
                'breakeven_triggered': False,
                'trailing_active': False,
                'trail_distance': 0.0,
                'entry_notional': order['cost'],
                'entry_time': datetime.now(timezone.utc)
            }
            log_state(f"Position created: {current_position}")
            
            # Place stop-loss with retry logic
            sl_placed = False
            for attempt in range(SL_RETRY_ATTEMPTS):
                try:
                    log_state(f"SL placement attempt {attempt + 1}/{SL_RETRY_ATTEMPTS}")
                    
                    sl_order = await exchange.create_order(
                        symbol=SYMBOL,
                        type='STOP_MARKET',
                        side='sell' if side == 'BUY' else 'buy',
                        amount=qty,
                        params={'stopPrice': sl_price, 'reduceOnly': True}
                    )
                    
                    stop_order_id = sl_order['id']
                    log_state(f"SL order placed: {stop_order_id} @ {sl_price:.2f}")
                    print(f"✅ Initial SL placed @ {sl_price:.2f} (ID: {stop_order_id})")
                    
                    # Wait and verify
                    await asyncio.sleep(SL_VERIFICATION_WAIT)
                    
                    open_orders = await exchange.fetch_open_orders(SYMBOL)
                    sl_found = any(o['id'] == stop_order_id for o in open_orders)
                    
                    if sl_found:
                        log_state(f"✅ Verified: SL exists in open orders")
                        sl_placed = True
                        break
                    else:
                        log_state(f"WARNING: SL order {stop_order_id} not found in open orders (attempt {attempt + 1})")
                        if attempt < SL_RETRY_ATTEMPTS - 1:
                            # Cancel any phantom order and retry
                            try:
                                await exchange.cancel_order(stop_order_id, SYMBOL)
                            except:
                                pass
                            await asyncio.sleep(1)
                
                except Exception as e:
                    log_state(f"SL placement error (attempt {attempt + 1}): {e}")
                    if attempt < SL_RETRY_ATTEMPTS - 1:
                        await asyncio.sleep(1)
            
            if not sl_placed:
                log_state("⚠️ CRITICAL: Stop-loss order could not be verified!")
                print("⚠️ WARNING: Stop-loss order may not be active!")
            
            # Log entry trade
            log_trade(side, current_position['entry_price'], None, qty, 0.0, 0.0, "ENTRY")
            
        finally:
            processing_signal = False

# ════════════════════════════════════════════════════════════════════════════
# EXIT LOGIC
# ════════════════════════════════════════════════════════════════════════════
async def update_trailing_or_close(current_price: float, atr: float):
    """Update trailing stop or close position"""
    global current_position, stop_order_id
    
    if not current_position:
        return
    
    side = current_position['side']
    entry_price = current_position['entry_price']
    initial_risk = current_position['initial_risk']
    
    if side == 'long':
        pnl_in_r = (current_price - entry_price) / initial_risk
    else:
        pnl_in_r = (entry_price - current_price) / initial_risk
    
    # Breakeven
    if pnl_in_r >= BREAKEVEN_TRIGGER_R and not current_position['breakeven_triggered']:
        new_sl = entry_price
        if side == 'short':
            new_sl = entry_price
        
        await move_stop_loss(new_sl)
        current_position['breakeven_triggered'] = True
        current_position['sl_price'] = new_sl
        log_state(f"Breakeven triggered @ {pnl_in_r:.2f}R | SL moved to {new_sl:.2f}")
        print(f"🔒 Breakeven triggered | SL → {new_sl:.2f}")
    
    # Trailing activation
    if pnl_in_r >= TRAIL_ACTIVATE_AT_R and not current_position['trailing_active']:
        current_position['trailing_active'] = True
        current_position['trail_distance'] = atr * TRAIL_DISTANCE_MULT
        log_state(f"Trailing activated @ {pnl_in_r:.2f}R | Distance: {current_position['trail_distance']:.2f}")
        print(f"📈 Trailing activated | Distance: {current_position['trail_distance']:.2f}")
    
    # Update trailing stop
    if current_position['trailing_active']:
        trail_dist = current_position['trail_distance']
        if side == 'long':
            new_sl = current_price - trail_dist
            if new_sl > current_position['sl_price']:
                await move_stop_loss(new_sl)
                current_position['sl_price'] = new_sl
                log_state(f"Trailing SL moved to {new_sl:.2f}")
                print(f"  ↗️ Trailing SL moved to {new_sl:.2f}")
        else:
            new_sl = current_price + trail_dist
            if new_sl < current_position['sl_price']:
                await move_stop_loss(new_sl)
                current_position['sl_price'] = new_sl
                log_state(f"Trailing SL moved to {new_sl:.2f}")
                print(f"  ↘️ Trailing SL moved to {new_sl:.2f}")

async def move_stop_loss(new_sl_price: float):
    """Update stop-loss order"""
    global stop_order_id, current_position
    
    if not stop_order_id:
        return
    
    try:
        await exchange.cancel_order(stop_order_id, SYMBOL)
        await asyncio.sleep(0.3)
    except:
        pass
    
    try:
        sl_order = await exchange.create_order(
            symbol=SYMBOL,
            type='STOP_MARKET',
            side='sell' if current_position['side'] == 'long' else 'buy',
            amount=current_position['quantity'],
            params={'stopPrice': new_sl_price, 'reduceOnly': True}
        )
        stop_order_id = sl_order['id']
        log_state(f"SL updated to {new_sl_price:.2f} (ID: {stop_order_id})")
    except Exception as e:
        log_state(f"SL update failed: {e}")
        print(f"❌ SL update failed: {e}")

async def close_position(reason: str, exit_price: float = None):
    """Close position and log trade"""
    global current_position, stop_order_id
    
    if not current_position:
        return
    
    side = current_position['side']
    entry = current_position['entry_price']
    qty = current_position['quantity']
    
    if not exit_price:
        # Get current price
        ticker = await exchange.fetch_ticker(SYMBOL)
        exit_price = ticker['last']
    
    if side == 'long':
        pnl = (exit_price - entry) * qty
    else:
        pnl = (entry - exit_price) * qty
    
    pnl_pct = (pnl / (entry * qty)) * 100 * LEVERAGE
    
    log_state(f"Position closed: {reason} | Exit: {exit_price:.2f} | PNL: {pnl:.2f}")
    print(f"🔔 CLOSED: {reason}")
    print(f"   Exit: {exit_price:.2f} | PNL: {'+' if pnl >= 0 else ''}{pnl:.2f} USDT ({'+' if pnl_pct >= 0 else ''}{pnl_pct:.2f}%)")
    
    log_trade(
        side='BUY' if side == 'long' else 'SELL',
        entry=entry,
        exit_price=exit_price,
        qty=qty,
        pnl=pnl,
        pnl_pct=pnl_pct,
        reason=reason
    )
    
    try:
        await exchange.create_order(
            symbol=SYMBOL,
            type='market',
            side='sell' if side == 'long' else 'buy',
            amount=qty,
            params={'reduceOnly': True}
        )
    except Exception as e:
        log_state(f"Close failed: {e}")
        print(f"❌ Close failed: {e}")
    
    await cancel_all_orders()
    current_position = None
    stop_order_id = None
    log_state("Position state cleared")

# ════════════════════════════════════════════════════════════════════════════
# CANDLE TIMING HELPER
# ════════════════════════════════════════════════════════════════════════════
def is_candle_closed(candle_timestamp, timeframe='3m'):
    """Check if candle is truly closed"""
    tf_seconds = {'1m': 60, '3m': 180, '5m': 300, '15m': 900, '1h': 3600}[timeframe]
    candle_time = candle_timestamp.timestamp() if isinstance(candle_timestamp, datetime) else candle_timestamp / 1000
    current_time = time.time()
    time_in_candle = current_time - candle_time
    progress = time_in_candle / tf_seconds
    return progress >= CANDLE_CLOSE_THRESHOLD

# ════════════════════════════════════════════════════════════════════════════
# MAIN LOOP (IMPROVED WITH LOCK)
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
    print(f"UNIFIED TRADING BOT V3 STARTED (RACE CONDITION FIXED)")
    print(f"Symbol: {SYMBOL} | Timeframe: {TIMEFRAME} | Leverage: {LEVERAGE}x")
    print(f"Strategy: RSI + Bollinger Bands + Volume")
    print(f"Fixes: Race Conditions, SL Verification, State Sync")
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
    print("✅ Main trading loop started\n")

    last_candle_time = None

    while True:
        try:
            # Periodic state reconciliation
            current_time = time.time()
            if current_time - last_reconcile_time >= RECONCILE_INTERVAL_SEC:
                await reconcile_state()
                last_reconcile_time = current_time

            # POLL latest candle (timeout fallback from watch_ohlcv)
            try:
                ohlcv_list = await asyncio.wait_for(
                    exchange.watch_ohlcv(SYMBOL, TIMEFRAME),
                    timeout=10  # 10s timeout
                )
                candle = ohlcv_list[-1]
            except asyncio.TimeoutError:
                # Fallback to polling
                log_state("watch_ohlcv timeout - falling back to polling")
                ohlcv_list = await exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, limit=1)
                candle = ohlcv_list[-1]
            
            ts_ms = candle[0]
            ts_dt = pd.to_datetime(ts_ms, unit='ms')
            
            # Skip if this is the same candle we just processed
            if last_candle_time == ts_ms:
                await asyncio.sleep(0.5)
                continue
            
            last_candle_time = ts_ms
            print(f"📊 [{ts_dt.strftime('%H:%M:%S UTC')}] {SYMBOL} | Close: {candle[4]:.2f}")

            # Update or append candle
            if not price_df.empty and price_df['timestamp'].iloc[-1] == ts_dt:
                price_df.loc[price_df.index[-1], ['open','high','low','close','volume']] = candle[1:6]
            else:
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

            # Check for signals on CLOSED candles only
            if ts_dt != last_processed_candle_time:
                if is_candle_closed(ts_dt, TIMEFRAME):
                    last_processed_candle_time = ts_dt
                    
                    # Only process signal if not already processing
                    if not processing_signal and not current_position and len(price_df) >= MIN_CANDLES_FOR_IND:
                        signal = detect_signal(price_df)

                        if signal in ['BUY', 'SELL'] and atr:
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
            print("\n  Stopped by user.")
            break
        except Exception as e:
            log_state(f"Main loop error: {e}")
            print(f"❌ Error: {e}")
            await asyncio.sleep(5)

    # Cleanup on exit
    try:
        if current_position:
            await close_position("Manual stop", None)
        await cancel_all_orders()
        await exchange.close()
        print("✅ Bot stopped gracefully")
    except Exception as e:
        print(f"Cleanup error: {e}")

if __name__ == "__main__":
    asyncio.run(main_loop())
