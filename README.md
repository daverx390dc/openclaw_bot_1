# Crypto Trading Bot - ETH/USDT Futures

Autonomous 24/7 trading bot for Binance Futures with RSI + Bollinger Bands + Volume strategy.

## 🚀 Features

- **Real-time signal generation** - RSI, Bollinger Bands, Volume analysis
- **Trailing stop-loss** - Dynamic risk management with breakeven protection
- **24/7 autonomous operation** - Auto-restart on crashes, health monitoring
- **Trade logging** - Full P&L tracking
- **Testnet support** - Paper trading before going live

## 📁 Project Structure

```
crypto-trading-bot/
├── agent.py                    # Main autonomous agent (run this!)
├── strategies/
│   ├── signal_generator.py     # Signal generation (RSI+BB+Volume)
│   ├── trailing_trade.py       # Order execution with trailing SL
│   └── unified_trading_bot.py  # Complete bot (used by agent)
├── config/
│   ├── api_keys.py            # API credentials (⚠️ ROTATE EXPOSED KEYS!)
│   ├── risk_params.json       # Position size, leverage, stops
│   └── trading_config.json    # Timeframes, indicators, thresholds
├── logs/
│   ├── agent.log              # Agent monitoring log
│   └── trades/trade_log.txt   # Trade history with P&L
└── data/
    └── agent_state.json       # Bot state (restarts, uptime)
```

## ⚙️ Setup

### 1. Install Dependencies

```bash
pip install ccxt ccxt.pro pandas numpy talib
```

**Note:** TA-Lib requires system libraries. Install:
- **Ubuntu/Debian:** `sudo apt-get install ta-lib`
- **macOS:** `brew install ta-lib`
- **Windows:** Download from [TA-Lib releases](https://github.com/cgohlke/talib-build/releases)

### 2. Configure API Keys

**⚠️ CRITICAL:** Your API keys were exposed in chat. Rotate them immediately:

1. Go to [Binance Futures Testnet](https://testnet.binancefuture.com/)
2. Generate new API keys
3. Update `config/api_keys.py`:

```python
API_KEY = 'your_new_testnet_key'
API_SECRET = 'your_new_testnet_secret'
```

### 3. Adjust Risk Parameters (Optional)

Edit `config/risk_params.json`:

```json
{
  "position_size_usdt": 500,      // Size per trade
  "leverage": 10,                 // Leverage multiplier
  "max_daily_loss_usdt": 100,     // Daily loss limit
  "initial_sl_multiplier": 1.1,   // Initial stop-loss distance (ATR multiplier)
  "breakeven_trigger_r": 1.0,     // Move SL to breakeven at 1R profit
  "trailing_activate_at_r": 1.5,  // Activate trailing at 1.5R profit
  "trailing_distance_multiplier": 1.8  // Trailing distance (ATR multiplier)
}
```

## 🏃 Running the Bot

### Start the Agent (Recommended)

The agent monitors the bot 24/7 and restarts on crashes:

```bash
cd crypto-trading-bot
python3 agent.py
```

**What the agent does:**
- ✅ Starts the trading bot
- ✅ Monitors health every 60 seconds
- ✅ Auto-restarts on crashes (max 5/hour)
- ✅ Logs all activity to `logs/agent.log`
- ✅ Tracks uptime and restart count

### Run Bot Directly (For Testing)

```bash
python3 strategies/unified_trading_bot.py
```

### Run in Background (Linux/macOS)

```bash
nohup python3 agent.py > /dev/null 2>&1 &
```

### Run as Systemd Service (Recommended for VPS)

Create `/etc/systemd/system/trading-bot.service`:

```ini
[Unit]
Description=Crypto Trading Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/crypto-trading-bot
ExecStart=/usr/bin/python3 /path/to/crypto-trading-bot/agent.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable trading-bot
sudo systemctl start trading-bot
sudo systemctl status trading-bot
```

## 📊 Monitoring

### View Logs

```bash
# Agent log (health checks, restarts)
tail -f logs/agent.log

# Trade log (entries, exits, P&L)
tail -f logs/trades/trade_log.txt
```

### Check Bot Status

The agent prints status every minute:

```
[2026-02-07 15:30:00 UTC] [INFO] ✓ Bot healthy | Uptime: 2.3h | Restarts: 0
```

### Trade Log Format

```
Timestamp | Side | Entry | Exit | Qty | PNL USDT | PNL % | Reason
2026-02-07 15:25:30 UTC | Side: BUY | Entry: 3250.50 | Exit: N/A | Qty: 0.1538 | PNL: +0.00 USDT (+0.00%) | Reason: ENTRY
2026-02-07 16:10:15 UTC | Side: BUY | Entry: 3250.50 | Exit: 3270.20 | Qty: 0.1538 | PNL: +3.03 USDT (+0.61%) | Reason: Trailing SL
```

## 🔧 Troubleshooting

### Bot Keeps Restarting

Check `logs/agent.log` for errors. Common issues:
- Invalid API keys
- Insufficient testnet balance
- Network connectivity
- Missing dependencies

### No Signals Generated

- Check if price data is streaming (`logs/agent.log` shows candle updates)
- Ensure at least 100 candles are loaded for indicators
- Verify RSI/BB/Volume conditions are being met
- Try lowering thresholds in `config/trading_config.json`

### API Errors

```
ccxt.errors.AuthenticationError
```
→ **Solution:** Rotate API keys (see Setup step 2)

```
ccxt.errors.InsufficientFunds
```
→ **Solution:** Get testnet USDT from [Binance Testnet Faucet](https://testnet.binancefuture.com/)

### TA-Lib Import Error

```
ImportError: cannot import name 'talib'
```
→ **Solution:** Install system TA-Lib library (see Setup step 1)

## 🎯 Strategy Details

### Entry Signals

**BUY:**
- RSI > 50 and rising (previous >= 40)
- Price above BB middle band
- Volume > 1.5x average
- Price breaking above BB upper band OR expanding volatility

**SELL:**
- RSI < 50 and falling (previous <= 60)
- Price below BB middle band
- Volume > 1.5x average
- Price breaking below BB lower band OR expanding volatility

### Risk Management

1. **Initial Stop-Loss:** 1.1 × ATR from entry
2. **Breakeven:** Move SL to entry at +1R profit
3. **Trailing:** Activate at +1.5R, trail at 1.8 × ATR distance
4. **Position Sizing:** $500 USDT × 10x leverage = ~0.15 ETH per trade

### Expected Performance (Backtesting Required)

⚠️ **This bot is NOT guaranteed profitable!** Always:
- Backtest on historical data first
- Paper trade for 2+ weeks
- Start with minimal position sizes
- Monitor closely for the first few days

## 🚨 Safety & Warnings

### 🔐 Security

- ✅ **NEVER commit `config/api_keys.py` to git**
- ✅ **Use testnet keys for testing**
- ✅ **Enable API key IP restrictions**
- ✅ **Disable withdrawals on API keys**

### 💰 Risk Disclaimer

- ❌ **Trading is risky** - You can lose money
- ❌ **No guarantees** - Past performance ≠ future results
- ❌ **Start small** - Test thoroughly before increasing size
- ❌ **Monitor actively** - Don't set and forget

### 🐛 Known Limitations

- Single asset only (ETH/USDT)
- No portfolio management
- No multi-timeframe confirmation
- No fundamental analysis
- Relies on technical indicators (lagging)

## 🛠️ Future Enhancements

Planned features:
- [ ] Multi-asset support
- [ ] Polymarket integration
- [ ] Telegram alerts
- [ ] Web dashboard
- [ ] Backtesting module
- [ ] Portfolio P&L tracking
- [ ] Advanced order types (iceberg, TWAP)
- [ ] Machine learning signal optimization

## 📞 Human Intervention Required

The agent handles:
- ✅ Restarting on crashes
- ✅ Monitoring health
- ✅ Logging all activity

You need to:
- 🔧 Update API keys when expired
- 🔧 Adjust risk params based on performance
- 🔧 Monitor logs daily
- 🔧 Approve strategy changes
- 🔧 Emergency stop if needed

## 🛑 Emergency Stop

To stop the bot immediately:

```bash
# Find the process
ps aux | grep agent.py

# Kill it
kill <PID>

# Or use Ctrl+C if running in foreground
```

If running as systemd service:

```bash
sudo systemctl stop trading-bot
```

**The agent will close all positions on shutdown.**

## 📝 License

This is personal trading software. Use at your own risk.

---

**Built with:** Python, CCXT, TA-Lib, Binance Futures API
**Last Updated:** 2026-02-07
