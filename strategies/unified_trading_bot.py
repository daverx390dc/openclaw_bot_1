# unified_trading_bot.py
# Real-time ETH/USDT Futures Trading Bot (Binance Testnet)
# Features: Internal signal calculation (RSI+BB+Volume) + Trailing SL + Trade logging
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

# Trading parameters
SYMBOL = 'ETH/USDT:USDT'
TIMEFRAME = '3m'
POSITION_SIZE_USDT = 500
LEVERAGE = 10

# Risk management
INITIAL_SL_MULT = 1.1
BREAKEVEN_TRIGGER_R = 1.0
TRAIL_ACTIVATE_AT_R = 1.5
TRAIL_DISTANCE_MULT = 1.8

# Indicator parameters
MIN_CANDLES_FOR_IND = 100
HISTORY_DAYS = 3

# Logging
TRADE_LOG_FILE = 'logs/trades/trade_log.txt'

# ════════════════════════════════════════════════════════════════════════════
# GLOBALS
# ════════════════════════════════════════════════════════════════════════════
current_position = None
exchange = None
stop_order_id = None
price_df = pd.DataFrame()  # Stores OHLCV data for indicators

# ════════════════════════════════════════════════════════════════════════════
# TRADE LOGGING
# ════════════════════════════════════════════════════════════════════════════
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
    """
    Detect BUY/SELL signals based on RSI, Bollinger Bands, and Volume
    Returns: 'BUY', 'SELL', or None
    """
    if len(df) < 2:
        return None

    # Check if indicators are available
    if pd.isna(df['rsi'].iloc[-1]) or pd.isna(df['bb_middle'].iloc[-1]):
        return None

    i = -1  # Current candle
    prev = -2  # Previous candle

    # ──── BUY SIGNAL ────
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
        return 'BUY'

    # ──── SELL SIGNAL ────
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

    # Auto-detect symbol
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
# HISTORICAL DATA LOADING
# ════════════════════════════════════════════════════════════════════════════
async def load_historical_data():
    """Load recent historical data for initial indicators"""
    try:
        since = int((datetime.utcnow() - timedelta(days=HISTORY_DAYS)).timestamp() * 1000)
        print(f"Fetching historical data since {datetime.utcfromtimestamp(since/1000)} UTC...")
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
# PRICE & ATR HELPERS
# ════════════════════════════════════════════════════════════════════════════
async def get_current_price():
    """Get real-time ticker price"""
    try:
        ticker = await exchange.fetch_ticker(SYMBOL)
        return float(ticker['last'])
    except Exception as e:
        print(f"Ticker error: {e}")
        return None


def get_atr_from_df(df):
    """Get ATR from dataframe"""
    if len(df) < 30 or 'atr' not in df.columns:
        return None
    atr = df['atr'].iloc[-1]
    return None if pd.isna(atr) else float(atr)


# ════════════════════════════════════════════════════════════════════════════
# ORDER MANAGEMENT
# ════════════════════════════════════════════════════════════════════════════
async def cancel_all_orders():
    """Cancel ALL open orders (not just stops) and VERIFY they're gone"""
    try:
        orders = await exchange.fetch_open_orders(SYMBOL)
        print(f"DEBUG: Found {len(orders)} total open orders")
        if len(orders) == 0:
            return True

        cancelled_count = 0
        for order in orders:
            try:
                await exchange.cancel_order(order['id'], SYMBOL)
                cancelled_count += 1
                print(f"✓ Cancelled order {order['id']} (type: {order['type']})")
            except Exception as e:
                print(f"⚠️ Failed to cancel {order['id']}: {e}")

        print(f"Total cancelled: {cancelled_count}/{len(orders)}")

        # VERIFY cancellation (retry up to 3 times)
        for attempt in range(3):
            await asyncio.sleep(0.5)
            remaining = await exchange.fetch_open_orders(SYMBOL)
            if len(remaining) == 0:
                print("✓ All orders successfully cancelled")
                return True
            else:
                print(f"⚠️ Attempt {attempt+1}: {len(remaining)} orders still open, retrying...")
                # Try cancelling remaining ones
                for order in remaining:
                    try:
                        await exchange.cancel_order(order['id'], SYMBOL)
                    except:
                        pass

        print(f"❌ WARNING: {len(remaining)} orders could not be cancelled after 3 attempts")
        return False
    except Exception as e:
        print(f"❌ Cancel failed: {e}")
        return False


async def verify_no_position():
    """Check if we actually have a position on the exchange"""
    try:
        positions = await exchange.fetch_positions([SYMBOL])
        active = next((p for p in positions if float(p.get('positionAmt', 0)) != 0), None)
        if active:
            amt = float(active['positionAmt'])
            print(f"⚠️ POSITION DETECTED: {amt} @ {active.get('entryPrice')}")
            return False  # We DO have a position
        return True  # No position
    except Exception as e:
        print(f"Position check failed: {e}")
        return True  # Assume no position on error


# ════════════════════════════════════════════════════════════════════════════
# POSITION ENTRY
# ════════════════════════════════════════════════════════════════════════════
async def place_entry(side: str, signal_price: float, atr: float):
    global current_position, stop_order_id
    risk_dist = INITIAL_SL_MULT * atr
    qty_raw = (POSITION_SIZE_USDT / signal_price) * LEVERAGE
    qty = exchange.amount_to_precision(SYMBOL, qty_raw)

    print(f"ENTRY → {side} | Signal price: {signal_price:.2f} | ATR: {atr:.2f} | Qty: {qty}")
    side_str = 'buy' if side == 'BUY' else 'sell'

    try:
        order = await exchange.create_market_order(SYMBOL, side_str, qty)
        print(f"ENTRY FILLED: {order}")
        entry_price = float(order.get('average') or order.get('price') or signal_price)
        notional = entry_price * float(qty)

        # Real SL based on actual fill price
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

        # Clean ALL old orders + place new initial SL
        await cancel_all_orders()
        sl_side = 'sell' if side == 'BUY' else 'buy'
        sl_order = await exchange.create_order(
            SYMBOL, 'STOP_MARKET', sl_side, qty, None,
            {'stopPrice': sl_price, 'reduceOnly': True, 'workingType': 'MARK_PRICE'}
        )
        stop_order_id = sl_order['id']
        print(f"Initial SL placed @ {sl_price:.2f}")

        # Log entry
        log_trade(side, entry_price, None, float(qty), "ENTRY")

    except Exception as e:
        print(f"Entry failed: {type(e).__name__} → {e}")


# ════════════════════════════════════════════════════════════════════════════
# TRAILING STOP-LOSS MANAGEMENT
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
        print(f"Breakeven triggered @ +{r_profit:.2f}R → SL @ {entry:.2f}")
        updated = True

    # Trailing activation
    if r_profit >= TRAIL_ACTIVATE_AT_R and not current_position['trailing_active']:
        current_position['trailing_active'] = True
        current_position['trail_distance'] = TRAIL_DISTANCE_MULT * atr
        print(f"Trailing activated @ +{r_profit:.2f}R | distance {current_position['trail_distance']:.2f}")
        updated = True

    # Trailing update
    if current_position['trailing_active']:
        if side == 'long':
            new_sl = price - current_position['trail_distance']
            if new_sl > current_position['sl_price'] + 0.3 * atr:
                current_position['sl_price'] = new_sl
                print(f"Trailing SL moved to {new_sl:.2f}")
                updated = True
        else:
            new_sl = price + current_position['trail_distance']
            if new_sl < current_position['sl_price'] - 0.3 * atr:
                current_position['sl_price'] = new_sl
                print(f"Trailing SL moved to {new_sl:.2f}")
                updated = True

    # Update SL order only if changed
    if updated:
        success = await cancel_all_orders()
        if not success:
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
            print(f"SL order updated @ {current_position['sl_price']:.2f}")
        except Exception as e:
            print(f"SL update failed: {e}")


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

    try:
        side_str = 'sell' if side == 'long' else 'buy'
        close_order = await exchange.create_market_order(
            SYMBOL, side_str, qty, params={'reduceOnly': True}
        )
        print(f"CLOSED {reason} | {qty:.4f} @ ~{price or 'market'}")
        close_price = price or float(close_order.get('average') or close_order.get('price') or entry_price)
        log_trade('BUY' if side == 'long' else 'SELL', entry_price, close_price, qty, reason)
    except Exception as e:
        print(f"Close failed: {e}")

    await cancel_all_orders()
    current_position = None
    stop_order_id = None


# ════════════════════════════════════════════════════════════════════════════
# MAIN LOOP
# ════════════════════════════════════════════════════════════════════════════
async def main_loop():
    global exchange, current_position, price_df

    # Initialize exchange
    exchange = await init_exchange()

    # Load historical data for initial indicators
    price_df = await load_historical_data()
    if not price_df.empty:
        compute_indicators(price_df)
        print(f"Initial indicators computed on {len(price_df)} candles")

    # Try to detect existing position
    try:
        positions = await exchange.fetch_positions([SYMBOL])
        active = next((p for p in positions if float(p.get('positionAmt', 0)) != 0), None)
        if active:
            print("!!! REAL POSITION FOUND ON EXCHANGE !!! Recovering...")
            amt = float(active['positionAmt'])
            side_str = 'long' if amt > 0 else 'short'
            current_position = {
                'side': side_str,
                'entry_price': float(active.get('entryPrice', 0)),
                'quantity': abs(amt),
                'initial_risk': 0.0,
                'sl_price': 0.0,
                'breakeven_triggered': False,
                'trailing_active': False,
                'trail_distance': 0.0,
            }
            print(f"Recovered {side_str} | Entry: {current_position['entry_price']:.2f} | Qty: {current_position['quantity']}")
        else:
            print("No active position found on exchange → starting clean")
    except Exception as e:
        print(f"Position recovery failed: {e} → starting clean")

    print(f"  {'═'*60}")
    print(f"UNIFIED TRADING BOT STARTED")
    print(f"Symbol: {SYMBOL} | Timeframe: {TIMEFRAME} | Leverage: {LEVERAGE}x")
    print(f"Strategy: RSI + Bollinger Bands + Volume")
    print(f"Press Ctrl+C to stop")
    print(f"{'═'*60}\n")

    # Create trade log header if needed
    if not os.path.exists(TRADE_LOG_FILE):
        os.makedirs(os.path.dirname(TRADE_LOG_FILE), exist_ok=True)
        with open(TRADE_LOG_FILE, 'w', encoding='utf-8') as f:
            f.write("Timestamp | Side | Entry | Exit | Qty | PNL USDT | PNL % | Reason\n")

    # CRITICAL: Clean up any orphan orders from previous runs
    print("  🧹 Cleaning up any orphan orders from previous runs...")
    await cancel_all_orders()
    await asyncio.sleep(1)

    last_candle_time = None
    last_cleanup_time = time.time()  # Track last cleanup

    while True:
        try:
            # Watch OHLCV via WebSocket
            ohlcv_list = await exchange.watch_ohlcv(SYMBOL, TIMEFRAME)
            candle = ohlcv_list[-1]
            ts_ms = candle[0]
            ts_dt = pd.to_datetime(ts_ms, unit='ms')

            # Update or append candle
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

                # Keep only recent data to avoid memory bloat
                if len(price_df) > 500:
                    price_df = price_df.iloc[-500:].reset_index(drop=True)

            # Compute indicators
            compute_indicators(price_df)
            price = float(candle[4])  # Close price
            atr = get_atr_from_df(price_df)

            # Manage existing position
            if current_position and atr:
                await update_trailing_or_close(price, atr)
                direction = "Long" if current_position['side'] == 'long' else "Short"
                # Correct PNL calculation
                if current_position['side'] == 'long':
                    pnl_raw = (price - current_position['entry_price']) * current_position['quantity']
                else:
                    pnl_raw = (current_position['entry_price'] - price) * current_position['quantity']
                pnl_sign = "+" if pnl_raw >= 0 else ""
                print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {direction} open @ {current_position['entry_price']:.2f} | "
                      f"Price: {price:.2f} | PNL: {pnl_sign}{pnl_raw:.2f} USDT | SL: {current_position['sl_price']:.2f}")

            # Periodic cleanup check (every 5 minutes) if no position
            if not current_position and (time.time() - last_cleanup_time > 300):
                print("  🧹 Periodic orphan order cleanup check...")
                await cancel_all_orders()
                last_cleanup_time = time.time()

            # Check for new signal (only on new candle close)
            if ts_dt != last_candle_time:
                last_candle_time = ts_dt
                if not current_position and len(price_df) >= MIN_CANDLES_FOR_IND:
                    signal = detect_signal(price_df)

                    # DEBUG: Show what we're seeing
                    if len(price_df) >= 2:
                        print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] "
                              f"Signal: {signal or 'None'} | "
                              f"Price: {price:.2f} | "
                              f"RSI: {price_df['rsi'].iloc[-1]:.1f} | "
                              f"Candles: {len(price_df)}")

                    if signal in ['BUY', 'SELL'] and atr:
                        # CRITICAL: Verify we actually have no position
                        has_no_position = await verify_no_position()
                        if not has_no_position:
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
                            print(f"⚠️ Signal {signal} ignored - insufficient balance (${usdt_free:.2f})")

            await asyncio.sleep(0.1)  # Small delay to prevent CPU hammering

        except KeyboardInterrupt:
            print("  Stopped by user.")
            break
        except Exception as e:
            print(f"Loop error: {type(e).__name__} → {str(e)}")
            await asyncio.sleep(5)

    # Cleanup
    if current_position:
        await close_position(reason="Script stopped")
    await exchange.close()
    print("Bot shutdown complete.")


# ════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    asyncio.run(main_loop())
