# live_trader_futures_testnet_trailing.py
# Real-time trading on Binance Futures TESTNET with trailing SL + breakeven
import asyncio
import ccxt.pro as ccxtpro
import time
import pandas as pd
import numpy as np
import talib
from datetime import datetime, timezone
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.api_keys import API_KEY, API_SECRET

# ────────────────────────────────────────────────
# CONFIG
# ────────────────────────────────────────────────
SYMBOL = 'ETH/USDT:USDT'
TIMEFRAME = '3m'
POSITION_SIZE_USDT = 500
LEVERAGE = 10
INITIAL_SL_MULT = 1.1
BREAKEVEN_TRIGGER_R = 1.0
TRAIL_ACTIVATE_AT_R = 1.5
TRAIL_DISTANCE_MULT = 1.8
POLL_INTERVAL_SEC = 15
TRADE_LOG_FILE = 'logs/trades/trade_log.txt'

# ────────────────────────────────────────────────
# Globals
current_position = None
exchange = None
stop_order_id = None


# ────────────────────────────────────────────────
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
    # Format prices properly
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


async def get_current_price_and_atr():
    """Get real-time ticker price"""
    try:
        ticker = await exchange.fetch_ticker(SYMBOL)
        return float(ticker['last'])
    except Exception as e:
        print(f"Ticker error: {e}")
        return None


async def get_atr():
    """Get ATR from historical data"""
    try:
        ohlcv = await exchange.fetch_ohlcv(SYMBOL, '5m', limit=100)
        if len(ohlcv) < 30:
            return None
        df = pd.DataFrame(ohlcv, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
        close = df['c'].astype(float).to_numpy()
        high = df['h'].astype(float).to_numpy()
        low = df['l'].astype(float).to_numpy()
        atr = float(talib.ATR(high, low, close, timeperiod=14)[-1])
        return None if np.isnan(atr) else atr
    except Exception as e:
        print(f"ATR error: {e}")
        return None


async def cancel_all_stop_orders():
    """Cancel all existing STOP orders and VERIFY they're gone"""
    try:
        orders = await exchange.fetch_open_orders(SYMBOL)
        print(f"DEBUG: Found {len(orders)} open orders")
        cancelled_count = 0
        for order in orders:
            print(f"DEBUG: Order {order['id']} type='{order['type']}'")
            # More flexible matching
            if 'STOP' in order['type'].upper():
                await exchange.cancel_order(order['id'], SYMBOL)
                cancelled_count += 1
                print(f"✓ Cancelled stop order: {order['id']}")
        print(f"Total cancelled: {cancelled_count}")

        # VERIFY cancellation
        await asyncio.sleep(0.5)  # Brief wait for exchange to process
        remaining = await exchange.fetch_open_orders(SYMBOL)
        stop_remaining = [o for o in remaining if 'STOP' in o['type'].upper()]
        if stop_remaining:
            print(f"⚠️ WARNING: {len(stop_remaining)} stop orders still active!")
            return False
        return True
    except Exception as e:
        print(f"❌ Cancel failed: {e}")
        return False


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

        # Clean old stops + place new initial SL
        await cancel_all_stop_orders()
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


async def update_trailing_or_close():
    global current_position, stop_order_id
    if not current_position:
        return

    price = await get_current_price_and_atr()
    if price is None:
        return
    atr = await get_atr()
    if atr is None:
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

    # Trailing update (only if meaningfully better)
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
        success = await cancel_all_stop_orders()
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

    await cancel_all_stop_orders()
    current_position = None
    stop_order_id = None


# ────────────────────────────────────────────────
# Signal source
# ────────────────────────────────────────────────
LAST_SIGNAL_ROW = -1


async def get_signal():
    global LAST_SIGNAL_ROW
    try:
        df = pd.read_csv('ethusdt_3m_rsi_bb_volume_signals_futures_3d.csv')
        if len(df) == 0:
            return None
        latest_idx = df.index[-1]
        if latest_idx <= LAST_SIGNAL_ROW:
            return None
        sig = str(df.iloc[-1].get('signal', '')).strip().upper()
        if sig in ['BUY', 'SELL']:
            LAST_SIGNAL_ROW = latest_idx
            print(f"New signal: {sig} (row {latest_idx})")
            return sig
    except Exception as e:
        print(f"CSV error: {e}")
    return None


async def main_loop():
    global exchange, current_position
    current_position = None  # ← force reset on every start
    exchange = await init_exchange()

    # Try to detect real position from exchange (not from old global state)
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

    print(f"  Starting Futures Testnet trailing bot for {SYMBOL}")
    print("Press Ctrl+C to stop\n")

    # header for log file
    if not os.path.exists(TRADE_LOG_FILE):
        os.makedirs(os.path.dirname(TRADE_LOG_FILE), exist_ok=True)
        with open(TRADE_LOG_FILE, 'w', encoding='utf-8') as f:
            f.write("Timestamp | Side | Entry | Exit | Qty | PNL USDT | PNL % | Reason\n")

    while True:
        try:
            signal = await get_signal()
            price = await get_current_price_and_atr()
            atr = await get_atr()

            if price is None or atr is None:
                await asyncio.sleep(POLL_INTERVAL_SEC)
                continue

            # Status line
            if current_position:
                await update_trailing_or_close()
                direction = "Long" if current_position['side'] == 'long' else "Short"
                # Correct PNL calculation for both LONG and SHORT
                if current_position['side'] == 'long':
                    pnl_raw = (price - current_position['entry_price']) * current_position['quantity']
                else:  # short
                    pnl_raw = (current_position['entry_price'] - price) * current_position['quantity']
                pnl_sign = "+" if pnl_raw >= 0 else ""
                print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {direction} open @ {current_position['entry_price']:.2f} | "
                      f"Price: {price:.2f} | PNL: {pnl_sign}{pnl_raw:.2f} USDT | SL: {current_position['sl_price']:.2f}")

            balance = await exchange.fetch_balance()
            usdt_free = balance.get('USDT', {}).get('free', 0)
            if usdt_free < POSITION_SIZE_USDT * 1.1:
                print("Skipping entry: low balance")
                await asyncio.sleep(POLL_INTERVAL_SEC)
                continue

            if signal in ['BUY', 'SELL'] and not current_position:
                print(f"  SIGNAL DETECTED: {signal} @ {price:.2f}")
                await place_entry(signal, price, atr)

            await asyncio.sleep(POLL_INTERVAL_SEC)

        except KeyboardInterrupt:
            print("  Stopped by user.")
            break
        except Exception as e:
            print(f"Loop error: {type(e).__name__} → {str(e)}")
            await asyncio.sleep(30)

    if current_position:
        await close_position(reason="Script stopped")
    await exchange.close()


if __name__ == "__main__":
    asyncio.run(main_loop())
