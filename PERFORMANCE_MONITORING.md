# Live Performance Monitoring

## 🎯 What You Asked For

You wanted a file that:
- ✅ Updates automatically when orders are placed and exited
- ✅ Shows total profit/loss
- ✅ Lets you monitor over 8 hours to verify the strategy works
- ✅ Matches your Binance demo account balance

**NOW YOU HAVE IT!** → `LIVE_PERFORMANCE.txt`

---

## 🚀 How to Use

### Option 1: Restart with Monitoring (Recommended)

**Stop current bot:**
```bash
cd ~/.openclaw/workspace/crypto-trading-bot
pkill -f agent.py
```

**Start with performance tracking:**
```bash
./start_with_monitoring.sh
```

This starts:
1. ✅ Trading bot agent
2. ✅ Performance tracker (updates LIVE_PERFORMANCE.txt every 10 seconds)

---

### Option 2: Add Tracker to Running Bot

If bot is already running, just add the tracker:

```bash
cd ~/.openclaw/workspace/crypto-trading-bot
nohup python3 utils/performance_tracker.py > logs/performance_tracker.log 2>&1 &
```

---

## 📊 Viewing Live Performance

### Quick Check (Snapshot)
```bash
cd ~/.openclaw/workspace/crypto-trading-bot
cat LIVE_PERFORMANCE.txt
```

### Live Dashboard (Auto-Refresh)
```bash
./check_performance.sh
```

This shows the dashboard and auto-refreshes every 5 seconds.

---

## 📈 What You'll See

```
======================================================================
            CRYPTO TRADING BOT - LIVE PERFORMANCE
======================================================================
Last Updated: 2026-02-07 16:55:00 UTC

📊 OVERALL PERFORMANCE
──────────────────────────────────────────────────────────────────────
Total Trades:        5
Wins:                3 ✅
Losses:              2 ❌
Win Rate:            60.0%

💰 PROFIT & LOSS
──────────────────────────────────────────────────────────────────────
Total P&L:           🟢 +$12.50 USDT

Average Win:         +$8.20
Average Loss:        $-3.10
Largest Win:         +$15.30
Largest Loss:        $-5.20

Profit Factor:       2.15x

📈 RECENT TRADES (Last 5)
──────────────────────────────────────────────────────────────────────
1. 2026-02-07 16:45 | BUY  | Entry: 3250.50 | Exit: 3265.20 | P&L: +$15.30 ✅
2. 2026-02-07 16:30 | SELL | Entry: 3240.00 | Exit: 3238.50 | P&L: +$2.30 ✅
3. 2026-02-07 16:15 | BUY  | Entry: 3235.20 | Exit: 3232.10 | P&L: -$3.10 ❌
4. 2026-02-07 16:00 | SELL | Entry: 3230.00 | Exit: 3235.20 | P&L: -$5.20 ❌
5. 2026-02-07 15:45 | BUY  | Entry: 3220.50 | Exit: 3228.50 | P&L: +$8.00 ✅

======================================================================
💡 TIP: Check your Binance testnet account balance to verify!
    https://testnet.binancefuture.com/
======================================================================
```

---

## ✅ Verifying Against Binance

**To confirm the bot is working correctly:**

1. **Check LIVE_PERFORMANCE.txt:**
   ```bash
   cat LIVE_PERFORMANCE.txt
   ```
   Note the "Total P&L" amount.

2. **Check your Binance Testnet account:**
   - Go to https://testnet.binancefuture.com/
   - Login
   - Check "Wallet" → "USDT Balance"

3. **Compare:**
   - Starting balance: ~10,000 USDT (testnet default)
   - Current balance: Starting balance + Total P&L
   - **They should match!**

**Example:**
- Starting: 10,000 USDT
- LIVE_PERFORMANCE.txt shows: +$12.50
- Binance should show: ~10,012.50 USDT ✅

---

## 📊 Performance Metrics Explained

| Metric | What It Means | Target |
|--------|---------------|--------|
| **Total Trades** | Number of completed trades | More data = better |
| **Win Rate** | % of profitable trades | >50% is good, >60% is great |
| **Total P&L** | Net profit/loss in USDT | Positive = profitable ✅ |
| **Average Win** | Average profit per winning trade | Higher is better |
| **Average Loss** | Average loss per losing trade | Lower is better |
| **Profit Factor** | Total wins / Total losses | >1.5 is good, >2.0 is great |

---

## ⏱️ 8-Hour Test Plan

**What to do:**

1. **Hour 0:** Start the bot with monitoring
   ```bash
   ./start_with_monitoring.sh
   cat LIVE_PERFORMANCE.txt  # Note starting values
   ```

2. **Hour 2, 4, 6:** Quick checks
   ```bash
   cat LIVE_PERFORMANCE.txt  # Check progress
   ```

3. **Hour 8:** Final evaluation
   ```bash
   cat LIVE_PERFORMANCE.txt  # Final results
   ```
   
   **Compare:**
   - If Total P&L is positive → Strategy is working! ✅
   - If Total P&L is negative → Need strategy adjustment ⚠️
   - If no trades → Market conditions didn't trigger signals (normal)

---

## 🔧 Troubleshooting

### LIVE_PERFORMANCE.txt not updating

**Check if tracker is running:**
```bash
ps aux | grep performance_tracker
```

**If not running, start it:**
```bash
cd ~/.openclaw/workspace/crypto-trading-bot
python3 utils/performance_tracker.py &
```

### Shows 0 trades after hours

**This is normal if:**
- Market is not volatile enough
- RSI/BB/Volume conditions not met
- It's a low-liquidity period

**Check bot is running:**
```bash
tail -20 logs/agent.log
```

Should show "✓ Bot healthy" messages.

---

## 🤖 What I'm Monitoring

While you watch LIVE_PERFORMANCE.txt, I'm also:

✅ Checking signal → order → exit flow
✅ Verifying trailing stop-loss works
✅ Looking for anomalies
✅ Researching better strategies
✅ Auto-fixing bugs
✅ Optimizing for maximum profit

**You focus on the results, I'll handle the improvements!**

---

## 📱 Quick Commands Reference

```bash
# View live dashboard
cat LIVE_PERFORMANCE.txt

# Auto-refresh dashboard
./check_performance.sh

# Check bot health
tail -20 logs/agent.log

# Check recent trades
tail -20 logs/trades/trade_log.txt

# Check if everything is running
ps aux | grep -E "(agent.py|performance_tracker)"

# Stop everything
pkill -f agent.py && pkill -f performance_tracker.py
```

---

## 🎯 Success Criteria (After 8 Hours)

**Strategy is working if:**
- ✅ Total P&L > $0
- ✅ Win Rate > 50%
- ✅ Profit Factor > 1.5
- ✅ Binance balance matches LIVE_PERFORMANCE.txt

**Need adjustment if:**
- ⚠️ Total P&L < $0
- ⚠️ Win Rate < 40%
- ⚠️ Profit Factor < 1.0

**In that case, I'll:**
1. Research better strategies
2. Adjust parameters
3. Implement improvements
4. Test again

---

**Ready to test?** Restart the bot with monitoring and check back in 8 hours! 🚀
