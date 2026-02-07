# realtime_ohlcv_binance_futures_testnet_rsi_bb_volume.py
# Streams ETHUSDT 1h (futures) from Binance TESTNET → computes RSI+BB+Volume signals → saves to CSV
import asyncio
import pandas as pd
import numpy as np
import ccxt.async_support as ccxt  # for historical fetch
import ccxt.pro as ccxtpro  # for websocket
import talib
from datetime import datetime, timedelta
import os
import time
from ccxt.pro import binanceusdm
from config.api_keys import API_KEY, API_SECRET

# ────────────────────────────────────────────────
# CONFIG
# ────────────────────────────────────────────────
SYMBOL = 'ETHUSDT'  # Futures notation (no slash)
TIMEFRAME = '3m'
HISTORY_DAYS = 3
CSV_PATH = f'ethusdt_{TIMEFRAME}_rsi_bb_volume_signals_futures_{HISTORY_DAYS}d.csv'
SAVE_EVERY = 10  # seconds between forced saves
MIN_CANDLES_FOR_IND = 100

# Set to True when you want to use real testnet API keys (for future execution logic)
USE_API_KEYS = True

# ────────────────────────────────────────────────
# Helper: Load historical futures data from TESTNET
# ────────────────────────────────────────────────
async def load_historical_data():
    exchange = ccxt.binanceusdm({'apiKey': API_KEY,
                                  'secret': API_SECRET,
                                  'enableRateLimit': True,
                                  'options': {
                                      'adjustForTimeDifference': True,
                                  },
                                  })
    # Activate testnet (sandbox mode)
    exchange.set_sandbox_mode(True)

    try:
        since = int((datetime.utcnow() - timedelta(days=HISTORY_DAYS)).timestamp() * 1000)
        print(f"Fetching historical futures data (testnet) since {datetime.utcfromtimestamp(since/1000)} UTC ...")
        ohlcv = []
        while since < int(time.time() * 1000):
            data = await exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, since=since, limit=1000)
            if not data:
                break
            ohlcv.extend(data)
            since = data[-1][0] + 1
            await asyncio.sleep(0.4)  # slightly longer delay for safety

        if not ohlcv:
            print("No historical data fetched.")
            return pd.DataFrame()

        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df.drop_duplicates(subset='timestamp', keep='last').reset_index(drop=True)
        print(f"Loaded {len(df)} historical 1h futures candles (testnet).")
        return df
    finally:
        await exchange.close()


# ────────────────────────────────────────────────
def compute_indicators(df):
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
    if 'signal' not in df.columns:
        df['signal'] = ''


def detect_signals(df):
    if len(df) < 2:
        return
    i = -1  # newest
    prev = -2

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
        print(f"     RSI {df['rsi'].iloc[i]:.1f}")
        print(f"     SL ≈ {sl:,.2f} | TP(1:3) ≈ {tp:,.2f}")
        df.iloc[i, df.columns.get_loc('signal')] = 'BUY'

    # SELL
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
        print(f"     RSI {df['rsi'].iloc[i]:.1f}")
        print(f"     SL ≈ {sl:,.2f} | TP(1:3) ≈ {tp:,.2f}")
        df.iloc[i, df.columns.get_loc('signal')] = 'SELL'


def backtest_signals(df):
    if len(df) < 50 or 'signal' not in df.columns:
        return
    print("Backtesting signals on historical futures data...")
    buy_count = sell_count = 0
    for idx in range(2, len(df)):
        i = idx
        prev = idx - 1
        rsi_buy = (df['rsi'].iloc[i] > 50) and (df['rsi'].iloc[i] > df['rsi'].iloc[prev]) and (df['rsi'].iloc[prev] >= 40)
        bb_buy = (df['close'].iloc[i] > df['bb_middle'].iloc[i]) and \
                 (df['close'].iloc[i] > df['bb_upper'].iloc[prev] or
                  (df['bb_upper'].iloc[i] - df['bb_lower'].iloc[i]) >
                  (df['bb_upper'].iloc[prev] - df['bb_lower'].iloc[prev]))
        volume_buy = df['volume'].iloc[i] > df['volume_sma'].iloc[i] * 1.5
        if rsi_buy and bb_buy and volume_buy:
            df.iloc[i, df.columns.get_loc('signal')] = 'BUY'
            print(f"Historical BUY at row {i}: {df['timestamp'].iloc[i]}")
            buy_count += 1

        rsi_sell = (df['rsi'].iloc[i] < 50) and (df['rsi'].iloc[i] < df['rsi'].iloc[prev]) and (df['rsi'].iloc[prev] <= 60)
        bb_sell = (df['close'].iloc[i] < df['bb_middle'].iloc[i]) and \
                  (df['close'].iloc[i] < df['bb_lower'].iloc[prev] or
                   (df['bb_upper'].iloc[i] - df['bb_lower'].iloc[i]) >
                   (df['bb_upper'].iloc[prev] - df['bb_lower'].iloc[prev]))
        volume_sell = df['volume'].iloc[i] > df['volume_sma'].iloc[i] * 1.5
        if rsi_sell and bb_sell and volume_sell:
            df.iloc[i, df.columns.get_loc('signal')] = 'SELL'
            print(f"Historical SELL at row {i}: {df['timestamp'].iloc[i]}")
            sell_count += 1

    print(f"Backtest complete. Found {buy_count + sell_count} signals (BUY: {buy_count}, SELL: {sell_count})")


async def main():
    # Load history from testnet futures
    df = await load_historical_data()
    if df.empty:
        df = pd.DataFrame(columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'rsi', 'bb_upper', 'bb_middle', 'bb_lower', 'atr', 'volume_sma', 'signal'
        ])
    else:
        if 'signal' not in df.columns:
            df['signal'] = ''

    if not df.empty:
        compute_indicators(df)
        backtest_signals(df)
        df.to_csv(CSV_PATH, index=False, float_format='%.8f')
        print(f"  Saved historical futures data + signals → {CSV_PATH}")

    exchange = None
    try:
        exchange = ccxtpro.binance({
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',  # ← futures
            },
        })
        # Activate TESTNET
        exchange.set_sandbox_mode(True)

        print(f"  Starting WebSocket stream for {SYMBOL} {TIMEFRAME} (Futures Testnet) ...")
        print("Signals will be marked in CSV column 'signal' ")

        last_save_time = time.time()
        while True:
            try:
                ohlcv_list = await exchange.watch_ohlcv(SYMBOL, TIMEFRAME)
                candle = ohlcv_list[-1]
                ts_ms = candle[0]
                ts_dt = pd.to_datetime(ts_ms, unit='ms')

                if not df.empty and df['timestamp'].iloc[-1] == ts_dt:
                    df.loc[df.index[-1], ['open','high','low','close','volume']] = candle[1:6]
                else:
                    new_row = {
                        'timestamp': ts_dt,
                        'open': float(candle[1]),
                        'high': float(candle[2]),
                        'low': float(candle[3]),
                        'close': float(candle[4]),
                        'volume': float(candle[5]),
                    }
                    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

                compute_indicators(df)
                detect_signals(df)

                current_time = time.time()
                if current_time - last_save_time >= SAVE_EVERY:
                    df.to_csv(CSV_PATH, index=False, float_format='%.8f')
                    print(f"  Saved {len(df)} rows → {CSV_PATH} ({df['timestamp'].iloc[-1]})")
                    last_save_time = current_time

            except Exception as e:
                print(f"Stream error: {type(e).__name__} → {str(e)}")
                await asyncio.sleep(5)

    except KeyboardInterrupt:
        print("  Stopped by user.")
    finally:
        if exchange:
            await exchange.close()
        if not df.empty:
            compute_indicators(df)
            detect_signals(df)
            df.to_csv(CSV_PATH, index=False, float_format='%.8f')
            print(f"  Final save → {len(df)} rows → {CSV_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
