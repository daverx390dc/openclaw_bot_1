# 🚀 Start Instructions for Fixed Trading Bot V3

## Quick Start (Run on Your Ubuntu Server)

```bash
# SSH into your Ubuntu server first
cd /home/ubuntu/.openclaw/workspace/crypto-trading-bot

# Make start script executable
chmod +x start_bot.sh

# Start the bot
bash start_bot.sh
```

## Verify Bot is Running

```bash
# Check process
ps aux | grep "agent.py"

# Watch logs in real-time
tail -f logs/agent.log

# Should see:
# ✅ Bot started (PID: XXXXX)
# UNIFIED TRADING BOT V3 STARTED (RACE CONDITION FIXED)
```

## Monitor Activity

```bash
# Terminal 1: Bot status
tail -f logs/agent.log

# Terminal 2: Trade activity  
tail -f logs/trades/trade_log.txt

# Terminal 3: State changes
tail -f logs/state_debug.log
```

## What to Look For (First Trade)

### ✅ Good Signs:
- `BUY signal detected` → **ONE** entry order (not 3)
- `✅ Verified: SL exists in open orders` 
- `Position created: {'side': 'long', ...}`
- No `DESYNC` warnings

### ❌ Red Flags:
- Multiple entry orders for same signal
- `WARNING: SL order not found`
- `DESYNC: We think we have long but exchange shows none`
- Bot stops/crashes

## Manual Commands

```bash
# Stop bot
pkill -f agent.py

# Restart bot
cd /home/ubuntu/.openclaw/workspace/crypto-trading-bot
bash start_bot.sh

# Check bot status
ps aux | grep agent.py

# View recent logs
tail -30 logs/agent.log
```

## Expected Behavior

1. **Bot starts:** Loads historical data, initializes
2. **Waits for signal:** Monitors 3m candles for RSI + BB + Volume conditions
3. **Signal detected:** 
   - Acquires entry lock (prevents duplicates)
   - Verifies no position exists
   - Places market entry
   - Places SL with 3 retry attempts
   - Verifies SL exists
4. **Position management:**
   - Monitors price every second
   - Moves SL to breakeven at +1R
   - Activates trailing at +1.5R
   - Updates trailing SL as price moves
5. **Exit:**
   - SL hit → logs trade with P&L
   - Manual stop → closes position gracefully

## Troubleshooting

### Bot Won't Start
```bash
# Check Python
python3 --version  # Should be 3.8+

# Check dependencies
pip3 list | grep ccxt

# Check logs for errors
tail -50 logs/agent.log
```

### Bot Crashes Immediately
```bash
# Run directly to see error
cd /home/ubuntu/.openclaw/workspace/crypto-trading-bot
python3 agent.py
```

### No Trades Happening
- **Normal:** May take hours for signal to trigger
- **Check:** Strategy is strict (RSI 30-55, BB lower, volume spike)
- **Verify:** Bot is running: `ps aux | grep agent`

### Duplicate Entries Still Happening
- **Check:** You're running V3 not V2
- **Verify:** `grep "V3 STARTED" logs/agent.log`
- **Fix:** Kill old instances: `pkill -f unified_trading_bot`

---

**Ready to start? SSH to your server and run:**
```bash
cd /home/ubuntu/.openclaw/workspace/crypto-trading-bot && bash start_bot.sh
```
