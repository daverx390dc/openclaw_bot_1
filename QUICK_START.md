# 🚀 Quick Start Guide - Trading Bot

## Prerequisites

Make sure you have:
- ✅ Virtual environment created with dependencies installed
- ✅ API keys configured in `config/api_keys.py`

---

## Start the Bot

```bash
cd /home/ubuntu/.openclaw/workspace/crypto-trading-bot
bash start_bot.sh
```

**What happens:**
- Stops any existing bot instances
- Archives old logs
- Starts the autonomous agent in the background
- Agent monitors and restarts bot if it crashes

**Output:**
```
✅ Agent started successfully (PID: 12345)

Monitor logs:
  tail -f logs/agent.log        # Agent & bot status
  tail -f logs/trades/trade_log.txt  # Trade history
  tail -f logs/state_debug.log  # Detailed state changes
```

---

## Stop the Bot

```bash
bash stop_bot.sh
```

Cleanly stops both the agent and trading bot.

---

## Check Status

```bash
bash check_status.sh
```

Shows:
- Agent status (running/stopped)
- Bot status (running/stopped)
- Recent logs
- Trade count and last 3 trades

---

## Monitor in Real-Time

### Main bot output:
```bash
tail -f logs/agent.log
```

### Trade activity:
```bash
tail -f logs/trades/trade_log.txt
```

### Detailed state changes:
```bash
tail -f logs/state_debug.log
```

---

## Troubleshooting

### Bot won't start:
```bash
# Check what's wrong
tail -50 logs/agent.log

# Try running bot directly to see error
source venv/bin/activate
python3 strategies/unified_trading_bot_v3.py
```

### Bot keeps restarting:
```bash
# Check logs for errors
grep -i "error\|warning\|failed" logs/agent.log

# Check API keys are correct
python3 test_demo_keys.py
```

### No trades happening:
- **Normal behavior** - strategy waits for specific conditions
- Can take hours for a signal to trigger
- Check `logs/agent.log` to see bot is monitoring correctly

---

## Important Commands

| Command | Action |
|---------|--------|
| `bash start_bot.sh` | Start bot in background |
| `bash stop_bot.sh` | Stop bot |
| `bash check_status.sh` | Check if running |
| `pkill -f agent.py` | Emergency stop |
| `tail -f logs/agent.log` | Watch logs |

---

## What to Expect

### On Start:
```
[BOT] UNIFIED TRADING BOT V3 STARTED (RACE CONDITION FIXED)
[BOT] Symbol: ETH/USDT:USDT | Timeframe: 3m | Leverage: 10x
[BOT] 🧹 Initial cleanup...
```

### During Operation:
```
✓ Bot healthy | Uptime: 2.3h | Restarts: 1
```

### When Signal Detected:
```
[BOT] 🚀 BUY SIGNAL @ 2,050.12 | 2026-02-08 01:30:00
[BOT] RSI 52.6 | ATR 12.08
[BOT] ✅ ENTRY FILLED: 8273407657
[BOT] ✅ Verified: SL exists in open orders
```

### Position Management:
```
[BOT] [01:30:45] Long @ 2050.31 | Price: 2055.20 | PNL: +11.92 | SL: 2037.03
[BOT] 📈 Trailing activated | Distance: 21.74
[BOT] ↗️ Trailing SL moved to 2040.50
```

---

## Files to Know

- `start_bot.sh` - Start bot in background
- `stop_bot.sh` - Stop bot
- `check_status.sh` - Check status
- `logs/agent.log` - Main log file
- `logs/trades/trade_log.txt` - All trades with P&L
- `logs/state_debug.log` - Detailed state changes
- `config/api_keys.py` - Your API credentials

---

**Ready? Run:** `bash start_bot.sh`
