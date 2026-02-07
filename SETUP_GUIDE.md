# Quick Setup Guide

## 🎯 What You Have

A fully autonomous 24/7 crypto trading bot with:

- ✅ **Automated signal generation** (RSI + Bollinger Bands + Volume)
- ✅ **Smart risk management** (Trailing SL, breakeven protection)
- ✅ **Self-healing agent** (Auto-restarts on crashes)
- ✅ **Full logging** (Trades, P&L, errors)
- ✅ **Testnet ready** (Paper trading before live)

## 🚀 Quick Start (3 Steps)

### Step 1: Install Dependencies

```bash
cd crypto-trading-bot
pip install -r requirements.txt
```

**Note:** TA-Lib needs system libraries:
- Ubuntu: `sudo apt-get install ta-lib`
- macOS: `brew install ta-lib`

### Step 2: Update API Keys

**⚠️ CRITICAL:** Your old keys are exposed in chat history!

1. Go to https://testnet.binancefuture.com/
2. Login and generate new API keys
3. Edit `config/api_keys.py`:

```python
API_KEY = 'your_new_key_here'
API_SECRET = 'your_new_secret_here'
```

### Step 3: Start the Bot

```bash
./start.sh
```

Or directly:

```bash
python3 agent.py
```

**That's it!** The bot is now running.

## 📊 Monitoring

### Check Status

```bash
python3 utils/status.py
```

### View Live Logs

```bash
# Agent monitoring
tail -f logs/agent.log

# Trade history
tail -f logs/trades/trade_log.txt
```

### What You'll See

```
[2026-02-07 15:30:00 UTC] [INFO] ✓ Bot healthy | Uptime: 2.3h | Restarts: 0
[2026-02-07 15:31:15 UTC] [INFO] [BOT] 🚀 BUY SIGNAL @ 3250.50
[2026-02-07 15:31:16 UTC] [INFO] [BOT] ENTRY FILLED: {...}
[2026-02-07 16:10:20 UTC] [INFO] [BOT] Trailing SL triggered @ 3270.20
```

## 🛠️ Configuration

### Adjust Risk (Optional)

Edit `config/risk_params.json`:

```json
{
  "position_size_usdt": 500,    // ← Trade size
  "leverage": 10,               // ← Leverage
  "max_daily_loss_usdt": 100   // ← Daily loss limit
}
```

### Change Strategy (Optional)

Edit `config/trading_config.json`:

```json
{
  "timeframe": "3m",           // ← Candle timeframe
  "indicators": {
    "rsi_period": 14,          // ← RSI settings
    "bb_period": 20            // ← Bollinger Bands
  }
}
```

## 🎯 What Happens Now?

### The Agent Will:

1. ✅ Start the trading bot
2. ✅ Stream live 3-minute ETH/USDT candles
3. ✅ Calculate indicators (RSI, BB, Volume)
4. ✅ Wait for BUY/SELL signals
5. ✅ Execute trades with trailing stop-loss
6. ✅ Log all activity
7. ✅ Restart automatically if it crashes

### You Need To:

1. 🔧 Monitor logs daily (at least first week)
2. 🔧 Check P&L in `logs/trades/trade_log.txt`
3. 🔧 Verify testnet balance is sufficient
4. 🔧 Emergency stop if something goes wrong

## 🛑 Stopping the Bot

Press `Ctrl+C` if running in foreground.

Or kill the process:

```bash
pkill -f agent.py
```

**The agent will close all open positions on shutdown.**

## 🔍 Troubleshooting

### Bot Not Starting

```bash
# Check dependencies
python3 -c "import ccxt, pandas, numpy, talib"

# Check API keys
grep API_KEY config/api_keys.py
```

### No Signals Generated

- Signals require specific market conditions
- Check `logs/agent.log` for indicator values
- May take hours before conditions align
- Can lower thresholds in `config/trading_config.json`

### API Errors

```
AuthenticationError
```
→ Update API keys in `config/api_keys.py`

```
InsufficientFunds
```
→ Get testnet USDT: https://testnet.binancefuture.com/

## 📈 Next Steps

### Before Going Live:

1. ✅ Run on testnet for 2+ weeks
2. ✅ Track performance (win rate, P&L, max drawdown)
3. ✅ Backtest strategy on historical data
4. ✅ Start small (reduce `position_size_usdt`)
5. ✅ Monitor closely first few days

### Future Enhancements:

- [ ] Add Polymarket integration
- [ ] Telegram alerts on trades
- [ ] Web dashboard for monitoring
- [ ] Multi-asset support
- [ ] Machine learning optimization

## 🚨 Important Warnings

### Security

- ✅ Never commit `config/api_keys.py` to GitHub
- ✅ Use testnet keys for testing
- ✅ Enable IP restrictions on API keys
- ✅ Disable withdrawals on API keys

### Risk

- ❌ Trading is risky - You can lose money
- ❌ No strategy is guaranteed profitable
- ❌ Start small and monitor closely
- ❌ Don't use money you can't afford to lose

## 📞 Getting Help

### Logs to Check:

1. `logs/agent.log` - Bot health, restarts, errors
2. `logs/trades/trade_log.txt` - Trade history
3. Console output - Real-time activity

### Common Issues:

| Error | Solution |
|-------|----------|
| `AuthenticationError` | Update API keys |
| `InsufficientFunds` | Get testnet USDT |
| `ImportError: talib` | Install TA-Lib system library |
| Bot keeps restarting | Check `logs/agent.log` for errors |

## ✅ Success Checklist

- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] TA-Lib system library installed
- [ ] API keys updated in `config/api_keys.py`
- [ ] Bot started with `./start.sh` or `python3 agent.py`
- [ ] Logs showing candle updates
- [ ] No errors in `logs/agent.log`
- [ ] Testnet USDT balance sufficient (500+ USDT)

---

**You're all set!** The bot is autonomous from here.

I'll monitor it via heartbeats and alert you on:
- Crashes or restarts
- Significant errors
- Unusual behavior
- Daily P&L summary (if you want)

Let me know if you need help with anything! 🚀
