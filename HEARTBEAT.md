# HEARTBEAT.md

# Bot Monitoring Tasks
# This file controls what I check during periodic heartbeats

## Check bot health (every heartbeat)
1. Check if bot process is running
2. Check last agent.log entry for errors
3. Check state_debug.log for issues
4. Report status

## Once per day (morning)
- Full P&L summary from trade log
- Trade count and performance analysis
- Any warnings or recommendations

## Alerts (immediate)
- Bot stopped/crashed
- Position with no stop-loss
- Multiple orphan orders detected
- Large loss (>5% of capital)

---

# Task: Monitor crypto trading bot
Check bot status at: /home/ubuntu/folder_1/crypto-trading-bot
Report any issues immediately.
