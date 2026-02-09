#!/home/ubuntu/.openclaw/workspace/live-crypto/myenv/bin/python
import asyncio
import ccxt.pro as ccxtpro
import pandas as pd
import numpy as np
import talib
from datetime import datetime, timezone, timedelta
import os
import time
import sys
import threading
from typing import Optional, Dict, Any

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
TRAIL_ACTIVATE_AT_R = 1.0  # Start trailing at +1.5R (change to 2.5 for bigger winners)
TRAIL_DISTANCE_MULT = 1.8  # Fixed trail distance (will be made dynamic)

# ═══ PROFIT MAXIMIZATION SETTINGS ═══
# Enable/disable advanced features
ENABLE_DYNAMIC_TRAILING = True      # Adjust trail distance based on profit
ENABLE_PARTIAL_EXITS = True         # Take partial profits at key levels
ENABLE_VOLATILITY_ADJUST = True     # Adapt to volatility changes

# Dynamic trailing distances (based on R-profit)
TRAIL_TIGHT = 1.5    # < 3R profit
TRAIL_MEDIUM = 1.8   # 3R - 6R profit  
TRAIL_LOOSE = 2.5    # > 6R profit (let big winners run)

# Partial exit settings (if ENABLE_PARTIAL_EXITS = True)
PARTIAL_EXIT_1_R = 2.0       # First exit at +2R
PARTIAL_EXIT_1_PCT = 0.40    # Close 40% of position
PARTIAL_EXIT_2_R = 4.0       # Second exit at +4R
PARTIAL_EXIT_2_PCT = 0.30    # Close 30% more (30% remains)

# After partial exits, trail remaining position with TRAIL_LOOSE distance

# ═══ MOMENTUM-BASED TRAILING (ADVANCED) ═══
ENABLE_MOMENTUM_TRAILING = True      # Tighten trail when momentum slows
MOMENTUM_LOOKBACK = 5                # Check momentum over last 5 candles
MOMENTUM_SLOW_THRESHOLD = 0.3        # If momentum drops 70%, tighten trail
MOMENTUM_TIGHT_MULT = 0.3            # Tighten trail to 0.8x ATR when slow

MIN_CANDLES_FOR_IND = 100
HISTORY_DAYS = 3

TRADE_LOG_FILE = 'logs/trades/trade_log.txt'
STATE_LOG_FILE = 'logs/state_debug.log'

# Timing and safety configs
CANDLE_CLOSE_THRESHOLD = 0.95
RECONCILE_INTERVAL_SEC = 30
MAX_ORPHAN_ORDER_AGE_SEC = 300

# NEW: Circuit breaker configs
MAX_SL_FAILURES = 3
MAX_NETWORK_FAILURES = 10
MAX_ORDER_CANCEL_FAILURES = 5
PARTIAL_FILL_TOLERANCE = 0.95  # Accept fills >= 95% of requested

# NEW: Order verification configs
ORDER_VERIFY_RETRIES = 5
ORDER_VERIFY_BACKOFF_BASE = 0.5  # 0.5s, 1s, 2s, 4s, 5s

# ════════════════════════════════════════════════════════════════════════════
# GLOBALS
# ════════════════════════════════════════════════════════════════════════════
current_position: Optional[Dict[str, Any]] = None
exchange = None
stop_order_id = None
price_df = pd.DataFrame()
last_processed_candle_time = None
last_reconcile_time = 0
order_history = {}  # {order_id: timestamp}

# NEW: Circuit breaker state
sl_placement_failures = 0
consecutive_network_failures = 0
consecutive_cancel_failures = 0
bot_halted = False

# NEW: Thread safety
df_lock = threading.Lock()
position_lock = threading.Lock()


# ════════════════════════════════════════════════════════════════════════════
# LOGGING
# ════════════════════════════════════════════════════════════════════════════
def log_state(message: str):
    """Debug log for state tracking"""
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    line = f"[{timestamp}] {message}\n"
    print(f"[STATE] {message}")
    try:
        os.makedirs(os.path.dirname(STATE_LOG_FILE), exist_ok=True)
        with open(STATE_LOG_FILE, 'a') as f:
            f.write(line)
    except Exception as e:
        print(f"[WARNING] Log write failed: {e}")


def log_trade(entry_side: str, entry_price: Optional[float], exit_price: Optional[float], 
              quantity: float, reason: str = ""):
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
    try:
        with open(TRADE_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(line)
    except Exception as e:
        print(f"[WARNING] Trade log write failed: {e}")


# ════════════════════════════════════════════════════════════════════════════
# CIRCUIT BREAKER
# ════════════════════════════════════════════════════════════════════════════
async def trigger_circuit_breaker(reason: str):
    """Emergency shutdown when critical failures occur"""
    global bot_halted
    
    log_state(f"🚨 CIRCUIT BREAKER TRIGGERED: {reason}")
    print(f"\n{'='*70}")
    print(f"🚨 CRITICAL FAILURE - BOT HALTING")
    print(f"Reason: {reason}")
    print(f"{'='*70}\n")
    
    bot_halted = True
    
    # Try to close position safely
    if current_position:
        try:
            await close_position(reason=f"Circuit breaker: {reason}")
        except Exception as e:
            log_state(f"Failed to close position during shutdown: {e}")
    
    # Close exchange connection
    if exchange:
        try:
            await exchange.close()
        except:
            pass
    
    print("Bot halted. Manual intervention required.")
    sys.exit(1)


# ════════════════════════════════════════════════════════════════════════════
# INDICATOR CALCULATION
# ════════════════════════════════════════════════════════════════════════════
def compute_indicators(df: pd.DataFrame):
    """Calculate RSI, Bollinger Bands, ATR, Volume SMA (thread-safe)"""
    if len(df) < MIN_CANDLES_FOR_IND:
        return
    
    try:
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
    except Exception as e:
        log_state(f"Indicator calculation error: {e}")


# ════════════════════════════════════════════════════════════════════════════
# SIGNAL DETECTION
# ════════════════════════════════════════════════════════════════════════════
def detect_signal(df: pd.DataFrame) -> Optional[str]:
    """Detect BUY/SELL signals - ONLY on completed candles (thread-safe)"""
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
    exchange.enableDemoTrading(False)  # LIVE MODE
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
async def load_historical_data() -> pd.DataFrame:
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
# ORDER VERIFICATION (NEW)
# ════════════════════════════════════════════════════════════════════════════
async def verify_order_exists(order_id: str, order_type: str = "order") -> bool:
    """
    Verify order exists in exchange with exponential backoff
    Returns: True if order confirmed, False otherwise
    """
    for attempt in range(ORDER_VERIFY_RETRIES):
        try:
            delay = min(ORDER_VERIFY_BACKOFF_BASE * (2 ** attempt), 5.0)
            await asyncio.sleep(delay)
            
            orders = await exchange.fetch_open_orders(SYMBOL)
            exists = any(o['id'] == order_id for o in orders)
            
            if exists:
                log_state(f"✅ {order_type} {order_id} verified (attempt {attempt + 1})")
                return True
            
            log_state(f"⏳ {order_type} {order_id} not found (attempt {attempt + 1}/{ORDER_VERIFY_RETRIES})")
            
        except Exception as e:
            log_state(f"Verification attempt {attempt + 1} failed: {e}")
    
    log_state(f"❌ {order_type} {order_id} verification failed after {ORDER_VERIFY_RETRIES} attempts")
    return False


# ════════════════════════════════════════════════════════════════════════════
# STATE RECONCILIATION
# ════════════════════════════════════════════════════════════════════════════
async def reconcile_state():
    """Cross-check internal state with exchange reality"""
    global current_position, stop_order_id, consecutive_cancel_failures
    
    log_state("=== STATE RECONCILIATION START ===")
    
    try:
        # 1. Get actual position from exchange
        positions = await exchange.fetch_positions([SYMBOL])
        exchange_position = next(
            (p for p in positions if float(p.get('contracts', p.get('positionAmt', 0))) != 0), 
            None
        )
        
        # 2. Get all open orders
        open_orders = await exchange.fetch_open_orders(SYMBOL)
        
        log_state(f"Exchange position: {exchange_position.get('contracts', exchange_position.get('positionAmt', 'N/A')) if exchange_position else 'None'}")
        log_state(f"Internal position: {current_position['side'] if current_position else 'None'}")
        log_state(f"Open orders: {len(open_orders)}")
        
        # Log detailed order info
        if open_orders:
            for order in open_orders:
                order_type = order.get('type', 'UNKNOWN')
                stop_price = order.get('stopPrice') or order.get('info', {}).get('stopPrice', 'N/A')
                amount = order.get('amount', 0)
                order_id = order.get('id', 'UNKNOWN')
                log_state(f"  Order: {order_type} @ {stop_price} | Amount: {amount} | ID: {order_id}")
        
        # Helper function to detect stop orders
        def is_stop_order(order):
            order_type = (order.get('type', '') or order.get('info', {}).get('type', '')).upper()
            return any(x in order_type for x in ['STOP_MARKET', 'STOP_LOSS', 'TAKE_PROFIT_MARKET', 'STOP'])
        
        # 3. CASE 1: Exchange has position, we don't know about it
        if exchange_position and not current_position:
            with position_lock:
                amt = float(exchange_position.get('contracts', exchange_position.get('positionAmt', 0)))
                entry_price = float(exchange_position.get('entryPrice', 0))
                
                print(f"⚠️ DESYNC DETECTED: Exchange has position we don't know about!")
                log_state(f"RECOVERY: Recovering position {amt} @ {entry_price}")
                
                # Calculate emergency stop-loss (3% from entry)
                emergency_sl = entry_price * (0.97 if amt > 0 else 1.03)
                emergency_risk = abs(entry_price - emergency_sl)
                
                current_position = {
                    'side': 'long' if amt > 0 else 'short',
                    'entry_price': entry_price,
                    'quantity': abs(amt),
                    'initial_risk': emergency_risk,
                    'sl_price': emergency_sl,
                    'breakeven_triggered': False,
                    'trailing_active': False,
                    'trail_distance': 0.0,
                }
                
                stop_orders = [o for o in open_orders if is_stop_order(o)]
                if stop_orders:
                    stop_order_id = stop_orders[0]['id']
                    sl_price = float(stop_orders[0].get('stopPrice') or stop_orders[0].get('info', {}).get('stopPrice') or 0)
                    if sl_price > 0:
                        current_position['sl_price'] = sl_price
                    log_state(f"✅ Found existing SL order: {stop_order_id} @ {current_position['sl_price']}")
                else:
                    log_state(f"⚠️ WARNING: Position has no stop-loss! Emergency SL set to {emergency_sl:.2f}")
        
        # 4. CASE 2: We think we have position, but exchange doesn't
        elif current_position and not exchange_position:
            with position_lock:
                print(f"⚠️ DESYNC: We think we have {current_position['side']} but exchange shows none")
                log_state(f"RECOVERY: Clearing phantom position")
                current_position = None
                stop_order_id = None
        
        # 5. CASE 3: Orphan orders (orders exist but no position)
        if not exchange_position and len(open_orders) > 0:
            print(f"🚨 ORPHAN ORDERS DETECTED: {len(open_orders)} orders with no position")
            log_state(f"CLEANUP: Cancelling ALL {len(open_orders)} orphan orders")
            
            failed_cancels = 0
            for order in open_orders:
                for attempt in range(3):
                    try:
                        await exchange.cancel_order(order['id'], SYMBOL)
                        log_state(f"✓ Cancelled orphan order: {order['id']}")
                        if order['id'] in order_history:
                            del order_history[order['id']]
                        break
                    except Exception as e:
                        if attempt == 2:
                            log_state(f"❌ Failed to cancel {order['id']} after 3 attempts: {e}")
                            failed_cancels += 1
                        else:
                            await asyncio.sleep(0.5)
            
            # Check circuit breaker
            if failed_cancels > 0:
                consecutive_cancel_failures += 1
                if consecutive_cancel_failures >= MAX_ORDER_CANCEL_FAILURES:
                    await trigger_circuit_breaker(f"Failed to cancel {failed_cancels} orphan orders")
            else:
                consecutive_cancel_failures = 0
            
            # Verify cleanup
            remaining = await exchange.fetch_open_orders(SYMBOL)
            if len(remaining) > 0:
                log_state(f"⚠️ WARNING: {len(remaining)} orders still remain")
            else:
                log_state(f"✓ Orphan order cleanup complete")
        
        # 6. CASE 4: Position exists but no/multiple stop-loss orders
        if current_position and exchange_position:
            stop_orders = [o for o in open_orders if is_stop_order(o)]
            
            if len(stop_orders) == 0:
                print(f"⚠️ CRITICAL: Position has NO STOP-LOSS!")
                log_state("RECOVERY: Position exists but no SL - emergency SL required")
                
                # Use existing emergency SL or set new one
                if current_position['sl_price'] == 0:
                    if current_position['side'] == 'long':
                        current_position['sl_price'] = current_position['entry_price'] * 0.97
                    else:
                        current_position['sl_price'] = current_position['entry_price'] * 1.03
                
                log_state(f"Emergency SL target: {current_position['sl_price']:.2f}")
                
            elif len(stop_orders) > 1:
                print(f"⚠️ WARNING: Multiple stop orders ({len(stop_orders)}) - cancelling extras")
                for order in stop_orders[1:]:
                    try:
                        await exchange.cancel_order(order['id'], SYMBOL)
                        log_state(f"Cancelled duplicate SL: {order['id']}")
                        if order['id'] in order_history:
                            del order_history[order['id']]
                    except Exception as e:
                        log_state(f"Failed to cancel duplicate SL: {e}")
        
        log_state("=== STATE RECONCILIATION COMPLETE ===")
        
    except Exception as e:
        log_state(f"Reconciliation error: {e}")
        print(f"❌ State reconciliation failed: {e}")


# ════════════════════════════════════════════════════════════════════════════
# ORDER MANAGEMENT
# ════════════════════════════════════════════════════════════════════════════
async def cancel_all_orders() -> bool:
    """Cancel ALL open orders with retry and verification"""
    global order_history, consecutive_cancel_failures
    
    try:
        for attempt in range(3):
            orders = await exchange.fetch_open_orders(SYMBOL)
            if len(orders) == 0:
                consecutive_cancel_failures = 0  # Reset on success
                return True
            
            log_state(f"Cancelling {len(orders)} orders (attempt {attempt+1})")
            
            failed = 0
            for order in orders:
                try:
                    await exchange.cancel_order(order['id'], SYMBOL)
                    log_state(f"Cancelled: {order['id']}")
                    if order['id'] in order_history:
                        del order_history[order['id']]
                except Exception as e:
                    log_state(f"Cancel failed for {order['id']}: {e}")
                    failed += 1
            
            if failed > 0:
                consecutive_cancel_failures += 1
            
            await asyncio.sleep(0.5)
        
        # Final verification
        remaining = await exchange.fetch_open_orders(SYMBOL)
        if len(remaining) > 0:
            log_state(f"⚠️ WARNING: {len(remaining)} orders remain after 3 attempts")
            consecutive_cancel_failures += 1
            
            if consecutive_cancel_failures >= MAX_ORDER_CANCEL_FAILURES:
                await trigger_circuit_breaker(f"Persistent order cancellation failures")
            
            return False
        
        consecutive_cancel_failures = 0
        return True
        
    except Exception as e:
        log_state(f"cancel_all_orders error: {e}")
        consecutive_cancel_failures += 1
        return False


async def emergency_cleanup_orphans() -> bool:
    """EMERGENCY: Aggressively clear ALL orphan orders"""
    global order_history
    
    try:
        log_state("🚨 EMERGENCY ORPHAN CLEANUP TRIGGERED")
        orders = await exchange.fetch_open_orders(SYMBOL)
        
        if len(orders) == 0:
            return True
        
        log_state(f"EMERGENCY: Clearing {len(orders)} orphan orders")
        
        failed_count = 0
        for order in orders:
            for attempt in range(5):
                try:
                    await exchange.cancel_order(order['id'], SYMBOL)
                    if order['id'] in order_history:
                        del order_history[order['id']]
                    log_state(f"✓ Emergency cleared: {order['id']}")
                    break
                except Exception as e:
                    if attempt < 4:
                        await asyncio.sleep(0.2)
                    else:
                        log_state(f"❌ Emergency cancel failed: {order['id']} - {e}")
                        failed_count += 1
        
        # Verify
        remaining = await exchange.fetch_open_orders(SYMBOL)
        log_state(f"Emergency cleanup result: {len(remaining)} orders remaining")
        
        success = len(remaining) == 0
        if not success and failed_count > 5:
            await trigger_circuit_breaker(f"Emergency cleanup failed: {failed_count} orders could not be cancelled")
        
        return success
        
    except Exception as e:
        log_state(f"Emergency cleanup error: {e}")
        return False


async def verify_no_position() -> bool:
    """Verify we have no position on exchange"""
    try:
        positions = await exchange.fetch_positions([SYMBOL])
        active = next(
            (p for p in positions if float(p.get('contracts', p.get('positionAmt', 0))) != 0), 
            None
        )
        if active:
            amt = float(active.get('contracts', active.get('positionAmt', 0)))
            log_state(f"Position check: FOUND {amt}")
            return False
        log_state("Position check: CLEAR")
        return True
    except Exception as e:
        log_state(f"Position check error: {e}")
        return True  # Assume clear on error (conservative)


def get_atr_from_df(df: pd.DataFrame) -> Optional[float]:
    """Get ATR from dataframe (thread-safe)"""
    if len(df) < 30 or 'atr' not in df.columns:
        return None
    atr = df['atr'].iloc[-1]
    return None if pd.isna(atr) else float(atr)


# ════════════════════════════════════════════════════════════════════════════
# POSITION ENTRY
# ════════════════════════════════════════════════════════════════════════════
async def place_entry(side: str, signal_price: float, atr: float):
    global current_position, stop_order_id, sl_placement_failures
    
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
        print(f"✅ ENTRY ORDER SUBMITTED: {order.get('id')}")
        log_state(f"Entry order submitted: {order}")
        
        # NEW: Handle partial fills
        filled_qty = float(order.get('filled', 0))
        requested_qty = float(qty)
        
        if filled_qty < requested_qty * PARTIAL_FILL_TOLERANCE:
            print(f"⚠️ PARTIAL FILL: Expected {requested_qty:.4f}, got {filled_qty:.4f}")
            log_state(f"PARTIAL FILL WARNING: {filled_qty}/{requested_qty}")
            
            if filled_qty < requested_qty * 0.5:  # Less than 50% filled
                print(f"❌ CRITICAL: Fill ratio too low ({filled_qty/requested_qty:.1%}) - aborting entry")
                log_state("Entry aborted - fill ratio below 50%")
                return
            
            # Adjust quantity to actual filled amount
            qty = exchange.amount_to_precision(SYMBOL, filled_qty)
            print(f"✓ Adjusted position size to filled amount: {qty}")
        
        entry_price = float(order.get('average') or order.get('price') or signal_price)
        notional = entry_price * float(qty)

        sl_price = entry_price - risk_dist if side == 'BUY' else entry_price + risk_dist

        with position_lock:
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
                # Partial exit tracking
                'partial_exit_1_done': False,
                'partial_exit_2_done': False,
                'remaining_quantity': float(qty),
            }
        
        log_state(f"Position created: {current_position}")

        # Place stop-loss with IMPROVED RETRY LOGIC
        sl_side = 'sell' if side == 'BUY' else 'buy'
        sl_placed = False
        
        for attempt in range(3):
            try:
                log_state(f"SL placement attempt {attempt+1}/3: price={sl_price:.2f}, side={sl_side}, qty={qty}")
                
                sl_order = await exchange.create_order(
                    SYMBOL, 'STOP_MARKET', sl_side, qty, None,
                    {
                        'stopPrice': sl_price,
                        'timeInForce': 'GTE_GTC',
                        'type': 'STOP_MARKET',
                        'reduceOnly': True
                    }
                )
                stop_order_id = sl_order['id']
                order_history[stop_order_id] = time.time()
                print(f"✅ Initial SL submitted @ {sl_price:.2f} (ID: {stop_order_id})")
                log_state(f"SL order submitted: {stop_order_id} @ {sl_price:.2f}")
                
                # NEW: Use verification function with exponential backoff
                if await verify_order_exists(stop_order_id, "SL"):
                    sl_placed = True
                    sl_placement_failures = 0  # Reset on success
                    break
                else:
                    log_state(f"⚠️ SL verification failed (attempt {attempt+1})")
                    if attempt < 2:
                        await asyncio.sleep(1)
            
            except Exception as e:
                log_state(f"SL attempt {attempt+1} failed: {type(e).__name__}: {e}")
                print(f"⚠️ SL placement attempt {attempt+1} failed: {e}")
                if attempt < 2:
                    await asyncio.sleep(1)
        
        if not sl_placed:
            sl_placement_failures += 1
            log_state(f"CRITICAL: SL placement failed ({sl_placement_failures}/{MAX_SL_FAILURES})")
            print(f"❌ CRITICAL: Failed to place stop-loss!")
            print(f"⚠️ Position is UNPROTECTED - Failure count: {sl_placement_failures}/{MAX_SL_FAILURES}")
            
            # NEW: Circuit breaker on repeated SL failures
            if sl_placement_failures >= MAX_SL_FAILURES:
                await trigger_circuit_breaker(f"{MAX_SL_FAILURES} consecutive SL placement failures")

        # Log entry
        log_trade(side, entry_price, None, float(qty), "ENTRY")

    except Exception as e:
        log_state(f"Entry failed: {e}")
        print(f"❌ Entry failed: {type(e).__name__} → {e}")


# ════════════════════════════════════════════════════════════════════════════
# MOMENTUM DETECTION
# ════════════════════════════════════════════════════════════════════════════
def detect_momentum_slowdown(df: pd.DataFrame, side: str, lookback: int = MOMENTUM_LOOKBACK) -> bool:
    """
    Detect if price momentum is slowing down (trend exhaustion)
    Returns True if momentum has decreased significantly
    """
    if not ENABLE_MOMENTUM_TRAILING or len(df) < lookback + 5:
        return False
    
    try:
        # Calculate recent price changes (momentum)
        recent_closes = df['close'].iloc[-lookback:].values
        
        # Average move per candle (recent)
        recent_moves = []
        for i in range(1, len(recent_closes)):
            move = abs(recent_closes[i] - recent_closes[i-1])
            recent_moves.append(move)
        
        recent_avg_move = np.mean(recent_moves) if recent_moves else 0
        
        # Compare to earlier momentum (5 candles before)
        earlier_closes = df['close'].iloc[-lookback*2:-lookback].values
        earlier_moves = []
        for i in range(1, len(earlier_closes)):
            move = abs(earlier_closes[i] - earlier_closes[i-1])
            earlier_moves.append(move)
        
        earlier_avg_move = np.mean(earlier_moves) if earlier_moves else 0
        
        # Avoid division by zero
        if earlier_avg_move == 0:
            return False
        
        # Calculate momentum ratio (recent vs earlier)
        momentum_ratio = recent_avg_move / earlier_avg_move
        
        # Momentum has slowed if ratio < threshold
        is_slow = momentum_ratio < MOMENTUM_SLOW_THRESHOLD
        
        if is_slow:
            log_state(f"Momentum slowdown detected: {momentum_ratio:.2f} (recent: {recent_avg_move:.2f}, earlier: {earlier_avg_move:.2f})")
        
        return is_slow
        
    except Exception as e:
        log_state(f"Momentum detection error: {e}")
        return False


def calculate_price_velocity(df: pd.DataFrame, periods: int = 3) -> float:
    """
    Calculate how fast price is moving (dollars per candle)
    Higher value = stronger momentum
    """
    if len(df) < periods + 1:
        return 0.0
    
    try:
        recent_prices = df['close'].iloc[-periods:].values
        price_changes = np.diff(recent_prices)
        avg_velocity = np.mean(np.abs(price_changes))
        return float(avg_velocity)
    except:
        return 0.0


# ════════════════════════════════════════════════════════════════════════════
# PROFIT MAXIMIZATION HELPERS
# ════════════════════════════════════════════════════════════════════════════
def get_dynamic_trail_distance(r_profit: float, atr: float, base_mult: float = TRAIL_DISTANCE_MULT) -> float:
    """
    Calculate trail distance based on profit level
    More profit = looser trail (let winners run)
    """
    if not ENABLE_DYNAMIC_TRAILING:
        return base_mult * atr
    
    if r_profit < 3.0:
        return TRAIL_TIGHT * atr  # Tight trail for small profits
    elif r_profit < 6.0:
        return TRAIL_MEDIUM * atr  # Medium trail
    else:
        return TRAIL_LOOSE * atr  # Loose trail for big winners


def get_volatility_adjusted_trail(current_atr: float, avg_atr: float, base_distance: float) -> float:
    """
    Adjust trail distance based on volatility changes
    High volatility = wider trail, Low volatility = tighter trail
    """
    if not ENABLE_VOLATILITY_ADJUST or avg_atr == 0:
        return base_distance
    
    volatility_ratio = current_atr / avg_atr
    
    if volatility_ratio > 1.5:
        # High volatility - widen trail by 40%
        return base_distance * 1.4
    elif volatility_ratio < 0.7:
        # Low volatility - tighten trail by 30%
        return base_distance * 0.7
    
    return base_distance


async def execute_partial_exit(exit_level: int, r_profit: float, price: float) -> bool:
    """
    Execute partial exit at specified R-level
    Returns True if executed successfully
    """
    if not ENABLE_PARTIAL_EXITS or not current_position:
        return False
    
    # Determine which partial exit
    if exit_level == 1:
        if current_position.get('partial_exit_1_done', False):
            return False
        r_target = PARTIAL_EXIT_1_R
        pct = PARTIAL_EXIT_1_PCT
    elif exit_level == 2:
        if current_position.get('partial_exit_2_done', False):
            return False
        r_target = PARTIAL_EXIT_2_R
        pct = PARTIAL_EXIT_2_PCT
    else:
        return False
    
    # Check if we've reached the target
    if r_profit < r_target:
        return False
    
    try:
        with position_lock:
            side = current_position['side']
            remaining_qty = current_position.get('remaining_quantity', current_position['quantity'])
            exit_qty = remaining_qty * pct
            exit_qty = exchange.amount_to_precision(SYMBOL, exit_qty)
            
            if float(exit_qty) < 0.001:  # Too small to exit
                return False
        
        # Execute partial exit
        side_str = 'sell' if side == 'long' else 'buy'
        order = await exchange.create_market_order(
            SYMBOL, side_str, exit_qty, params={'reduceOnly': True}
        )
        
        exit_price = float(order.get('average') or order.get('price') or price)
        
        with position_lock:
            new_remaining = remaining_qty - float(exit_qty)
            current_position['remaining_quantity'] = new_remaining
            
            if exit_level == 1:
                current_position['partial_exit_1_done'] = True
            else:
                current_position['partial_exit_2_done'] = True
        
        # Calculate profit on this partial
        entry = current_position['entry_price']
        if side == 'long':
            partial_pnl = (exit_price - entry) * float(exit_qty)
        else:
            partial_pnl = (entry - exit_price) * float(exit_qty)
        
        print(f"✅ PARTIAL EXIT #{exit_level} @ +{r_profit:.2f}R")
        print(f"   Closed: {exit_qty} ({pct*100:.0f}%) @ {exit_price:.2f}")
        print(f"   Profit: +${partial_pnl:.2f} | Remaining: {new_remaining:.4f}")
        log_state(f"Partial exit {exit_level}: {exit_qty} @ {exit_price:.2f}, PNL: +${partial_pnl:.2f}")
        
        # Log partial exit
        log_trade(
            'BUY' if side == 'long' else 'SELL',
            entry,
            exit_price,
            float(exit_qty),
            f"PARTIAL_EXIT_{exit_level} (+{r_profit:.2f}R)"
        )
        
        return True
        
    except Exception as e:
        log_state(f"Partial exit {exit_level} failed: {e}")
        print(f"⚠️ Partial exit {exit_level} failed: {e}")
        return False


# ════════════════════════════════════════════════════════════════════════════
# TRAILING STOP-LOSS
# ════════════════════════════════════════════════════════════════════════════
async def update_trailing_or_close(price: float, atr: float):
    global current_position, stop_order_id
    
    if not current_position:
        return

    with position_lock:
        entry = current_position['entry_price']
        side = current_position['side']
        risk = current_position['initial_risk']
        qty = current_position.get('remaining_quantity', current_position['quantity'])

        # Skip if risk is 0 (recovered position) - emergency SL is already set
        if risk == 0:
            log_state("Position recovery mode: using emergency SL")
            return
        
        r_profit = (price - entry) / risk if side == 'long' else (entry - price) / risk
        updated = False

    # ═══ PARTIAL EXITS (NEW) ═══
    if ENABLE_PARTIAL_EXITS:
        # Try partial exit 1
        if r_profit >= PARTIAL_EXIT_1_R:
            await execute_partial_exit(1, r_profit, price)
        
        # Try partial exit 2
        if r_profit >= PARTIAL_EXIT_2_R:
            await execute_partial_exit(2, r_profit, price)

    with position_lock:
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
            
            # ═══ DYNAMIC TRAIL DISTANCE (NEW) ═══
            base_trail = get_dynamic_trail_distance(r_profit, atr)
            current_position['trail_distance'] = base_trail
            
            print(f"✅ Trailing activated @ +{r_profit:.2f}R | distance {current_position['trail_distance']:.2f}")
            log_state(f"Trailing activated: distance={current_position['trail_distance']:.2f}, r_profit={r_profit:.2f}")
            updated = True

        # Trailing update
        if current_position['trailing_active']:
            # ═══ DYNAMIC + VOLATILITY ADJUSTED TRAILING ═══
            base_trail = get_dynamic_trail_distance(r_profit, atr)
            
            # Get average ATR for volatility adjustment
            avg_atr = atr  # Default to current if can't calculate
            if 'atr' in price_df.columns and len(price_df) >= 50:
                with df_lock:
                    avg_atr = price_df['atr'].iloc[-50:].mean()
            
            adjusted_trail = get_volatility_adjusted_trail(atr, avg_atr, base_trail)
            
            # ═══ MOMENTUM-BASED TIGHTENING (NEW) ═══
            # If momentum is slowing, tighten the trail to catch the top/bottom
            momentum_slow = False
            if ENABLE_MOMENTUM_TRAILING and len(price_df) >= MOMENTUM_LOOKBACK + 5:
                with df_lock:
                    momentum_slow = detect_momentum_slowdown(price_df, side, MOMENTUM_LOOKBACK)
                
                if momentum_slow:
                    # Tighten trail significantly when momentum dies
                    momentum_trail = MOMENTUM_TIGHT_MULT * atr
                    if momentum_trail < adjusted_trail:
                        adjusted_trail = momentum_trail
                        print(f"🎯 MOMENTUM SLOW - Trail tightened to {adjusted_trail:.2f}")
                        log_state(f"Momentum tightening: trail={adjusted_trail:.2f}, r_profit={r_profit:.2f}")
            
            current_position['trail_distance'] = adjusted_trail
            
            if side == 'long':
                new_sl = price - current_position['trail_distance']
                if new_sl > current_position['sl_price'] + 0.1 * atr:
                    current_position['sl_price'] = new_sl
                    momentum_tag = " [MOMENTUM]" if momentum_slow else ""
                    print(f"📈 Trailing SL moved to {new_sl:.2f} (dist: {current_position['trail_distance']:.2f}, +{r_profit:.2f}R){momentum_tag}")
                    log_state(f"Trailing update: SL={new_sl:.2f}, r_profit={r_profit:.2f}, trail_dist={current_position['trail_distance']:.2f}, momentum_slow={momentum_slow}")
                    updated = True
            else:
                new_sl = price + current_position['trail_distance']
                if new_sl < current_position['sl_price'] - 0.3 * atr:
                    current_position['sl_price'] = new_sl
                    momentum_tag = " [MOMENTUM]" if momentum_slow else ""
                    print(f"📉 Trailing SL moved to {new_sl:.2f} (dist: {current_position['trail_distance']:.2f}, +{r_profit:.2f}R){momentum_tag}")
                    log_state(f"Trailing update: SL={new_sl:.2f}, r_profit={r_profit:.2f}, trail_dist={current_position['trail_distance']:.2f}, momentum_slow={momentum_slow}")
                    updated = True

    # Update SL order only if changed
    if updated:
        # Get all current orders
        all_orders = await exchange.fetch_open_orders(SYMBOL)
        
        # Cancel only STOP orders (not all orders)
        stop_orders = [o for o in all_orders if 'STOP' in o.get('type', '').upper()]
        
        for order in stop_orders:
            try:
                await exchange.cancel_order(order['id'], SYMBOL)
                log_state(f"Cancelled old SL: {order['id']}")
                if order['id'] in order_history:
                    del order_history[order['id']]
            except Exception as e:
                log_state(f"Failed to cancel old SL {order['id']}: {e}")
        
        await asyncio.sleep(0.5)
        
        stop_order_id = None
        sl_side = 'sell' if side == 'long' else 'buy'
        sl_updated = False
        
        for attempt in range(3):
            try:
                log_state(f"SL update attempt {attempt+1}/3: price={current_position['sl_price']:.2f}")
                
                new_sl_order = await exchange.create_order(
                    SYMBOL, 'STOP_MARKET', sl_side, qty, None,
                    {
                        'stopPrice': current_position['sl_price'],
                        'timeInForce': 'GTE_GTC',
                        'type': 'STOP_MARKET',
                        'reduceOnly': True
                    }
                )
                stop_order_id = new_sl_order['id']
                order_history[stop_order_id] = time.time()
                print(f"✅ SL order updated @ {current_position['sl_price']:.2f}")
                log_state(f"SL order updated: {stop_order_id} @ {current_position['sl_price']:.2f}")
                
                # NEW: Use verification function
                if await verify_order_exists(stop_order_id, "Updated SL"):
                    sl_updated = True
                    break
                else:
                    log_state(f"⚠️ Updated SL verification failed (attempt {attempt+1})")
                    if attempt < 2:
                        await asyncio.sleep(1)
            
            except Exception as e:
                log_state(f"SL update attempt {attempt+1} failed: {type(e).__name__}: {e}")
                if attempt < 2:
                    await asyncio.sleep(1)
        
        if not sl_updated:
            log_state(f"WARNING: SL update failed after 3 attempts")
            print(f"⚠️ SL update failed - position may be at risk")


# ════════════════════════════════════════════════════════════════════════════
# POSITION CLOSE
# ════════════════════════════════════════════════════════════════════════════
async def close_position(price: Optional[float] = None, reason: str = "Manual/SL/TP"):
    global current_position, stop_order_id
    
    if not current_position:
        return

    with position_lock:
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
    
    with position_lock:
        current_position = None
    stop_order_id = None
    order_history.clear()
    log_state("Position state cleared")


# ════════════════════════════════════════════════════════════════════════════
# CANDLE TIMING HELPER
# ════════════════════════════════════════════════════════════════════════════
def is_candle_closed(candle_timestamp, timeframe: str = '3m') -> bool:
    """Check if a candle is truly closed"""
    tf_seconds = {'1m': 60, '3m': 180, '5m': 300, '15m': 900, '1h': 3600}[timeframe]
    
    candle_time = candle_timestamp.timestamp() if isinstance(candle_timestamp, datetime) else candle_timestamp / 1000
    current_time = time.time()
    
    time_in_candle = current_time - candle_time
    progress = time_in_candle / tf_seconds
    
    return progress >= CANDLE_CLOSE_THRESHOLD


# ════════════════════════════════════════════════════════════════════════════
# ORDER HISTORY CLEANUP
# ════════════════════════════════════════════════════════════════════════════
def cleanup_old_order_history():
    """Remove order history entries older than 1 hour"""
    global order_history
    current_time = time.time()
    order_history = {k: v for k, v in order_history.items() if current_time - v < 3600}


# ════════════════════════════════════════════════════════════════════════════
# MAIN LOOP
# ════════════════════════════════════════════════════════════════════════════
async def main_loop():
    global exchange, current_position, price_df, last_processed_candle_time, last_reconcile_time
    global consecutive_network_failures, bot_halted

    exchange = await init_exchange()
    price_df = await load_historical_data()
    
    if not price_df.empty:
        with df_lock:
            compute_indicators(price_df)
        print(f"Initial indicators computed on {len(price_df)} candles")

    # Initial state reconciliation
    await reconcile_state()

    print(f"  {'═'*70}")
    print(f"🚀 HARDENED TRADING BOT V3 STARTED")
    print(f"Symbol: {SYMBOL} | Timeframe: {TIMEFRAME} | Leverage: {LEVERAGE}x")
    print(f"Strategy: RSI + Bollinger Bands + Volume")
    print(f"Protection: Circuit breakers, partial fill handling, network resilience")
    print(f"Press Ctrl+C to stop")
    print(f"{'═'*70}\n")

    if not os.path.exists(TRADE_LOG_FILE):
        os.makedirs(os.path.dirname(TRADE_LOG_FILE), exist_ok=True)
        with open(TRADE_LOG_FILE, 'w', encoding='utf-8') as f:
            f.write("Timestamp | Side | Entry | Exit | Qty | PNL USDT | PNL % | Reason\n")

    # Initial cleanup
    print("🧹 Initial cleanup...")
    await cancel_all_orders()
    await asyncio.sleep(1)

    while not bot_halted:
        try:
            # Periodic state reconciliation
            current_time = time.time()
            if current_time - last_reconcile_time >= RECONCILE_INTERVAL_SEC:
                await reconcile_state()
                last_reconcile_time = current_time
                
                # Cleanup old order history
                cleanup_old_order_history()
                
                # Check for orphan order accumulation
                open_orders = await exchange.fetch_open_orders(SYMBOL)
                if len(open_orders) > 10:
                    print(f"🚨 ORPHAN ORDER ALERT: {len(open_orders)} orders - emergency cleanup")
                    success = await emergency_cleanup_orphans()
                    if not success:
                        await trigger_circuit_breaker("Emergency cleanup failed with 10+ orphan orders")

            # Watch OHLCV via WebSocket (with timeout fallback)
            try:
                ohlcv_list = await asyncio.wait_for(
                    exchange.watch_ohlcv(SYMBOL, TIMEFRAME),
                    timeout=15.0
                )
                candle = ohlcv_list[-1]
                consecutive_network_failures = 0  # Reset on success
                
            except asyncio.TimeoutError:
                consecutive_network_failures += 1
                log_state(f"watch_ohlcv timeout (failure {consecutive_network_failures}/{MAX_NETWORK_FAILURES})")
                
                if consecutive_network_failures >= MAX_NETWORK_FAILURES:
                    await trigger_circuit_breaker(f"{MAX_NETWORK_FAILURES} consecutive network timeouts")
                
                # Fallback to polling
                ohlcv_list = await exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, limit=1)
                if not ohlcv_list:
                    await asyncio.sleep(1)
                    continue
                candle = ohlcv_list[-1]
            
            ts_ms = candle[0]
            ts_dt = pd.to_datetime(ts_ms, unit='ms')

            # Thread-safe DataFrame update
            with df_lock:
                if not price_df.empty and price_df['timestamp'].iloc[-1] == ts_dt:
                    # Update existing candle
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

            # Manage existing position (thread-safe read)
            if current_position and atr and len(price_df) >= MIN_CANDLES_FOR_IND:
                await update_trailing_or_close(price, atr)
                
                with position_lock:
                    direction = "Long" if current_position['side'] == 'long' else "Short"
                    remaining_qty = current_position.get('remaining_quantity', current_position['quantity'])
                    
                    if current_position['side'] == 'long':
                        pnl_raw = (price - current_position['entry_price']) * remaining_qty
                    else:
                        pnl_raw = (current_position['entry_price'] - price) * remaining_qty
                    
                    sl_price = current_position['sl_price']
                    
                    # Show partial exit status
                    partial_status = ""
                    if ENABLE_PARTIAL_EXITS:
                        if current_position.get('partial_exit_1_done', False):
                            partial_status = " [P1✓]"
                        if current_position.get('partial_exit_2_done', False):
                            partial_status += " [P2✓]"
                
                pnl_sign = "+" if pnl_raw >= 0 else ""
                print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {direction} @ {current_position['entry_price']:.2f}{partial_status} | "
                      f"Price: {price:.2f} | PNL: {pnl_sign}{pnl_raw:.2f} | SL: {sl_price:.2f}")

            # Signal detection on closed candles only
            if ts_dt != last_processed_candle_time:
                if is_candle_closed(ts_dt, TIMEFRAME):
                    last_processed_candle_time = ts_dt
                    
                    if not current_position and len(price_df) >= MIN_CANDLES_FOR_IND:
                        with df_lock:
                            signal = detect_signal(price_df)

                        if signal in ['BUY', 'SELL'] and atr:
                            # Pre-entry verification
                            has_no_position = await verify_no_position()
                            if not has_no_position:
                                log_state(f"Signal {signal} BLOCKED - position exists")
                                print(f"⚠️ Signal {signal} BLOCKED - position detected")
                                continue
                            
                            # Check orphan orders
                            open_orders = await exchange.fetch_open_orders(SYMBOL)
                            if len(open_orders) > 5:
                                log_state(f"Signal {signal} BLOCKED - {len(open_orders)} orphan orders")
                                print(f"⚠️ Signal {signal} BLOCKED - cleaning {len(open_orders)} orphan orders")
                                await emergency_cleanup_orphans()
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
    if exchange:
        await exchange.close()
    print("Bot shutdown complete.")


if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("\n✓ Bot stopped by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        log_state(f"FATAL: {e}")