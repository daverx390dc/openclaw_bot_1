# Monitoring Setup Guide

Your bot is running on **your machine** (`/home/ubuntu/folder_1/crypto-trading-bot`)  
OpenClaw agent runs on **different machine** (`/home/node/.openclaw/workspace`)

Since we're on separate systems, here are your monitoring options:

---

## ✅ Option 1: Quick Manual Check (Recommended)

**Run this whenever you want me to analyze the bot:**

```bash
cd /home/ubuntu/folder_1/crypto-trading-bot

# Generate summary
./utils/generate_summary.sh

# Output will be saved to /tmp/bot_summary_*.txt
# Copy the file path shown, then run:
cat /tmp/bot_summary_XXXXXX.txt
```

Then **copy/paste the output** into chat with me.

---

## ✅ Option 2: Automated Daily Summary

**Set up a cron job** to create daily summaries:

```bash
# Edit crontab
crontab -e

# Add this line (runs every day at 9 AM UTC):
0 9 * * * /home/ubuntu/folder_1/crypto-trading-bot/utils/sync_to_openclaw.sh

# Or every 4 hours:
0 */4 * * * /home/ubuntu/folder_1/crypto-trading-bot/utils/sync_to_openclaw.sh
```

**Then once a day, just paste the summary:**

```bash
cat /tmp/openclaw_bot_status.txt
```

---

## ✅ Option 3: Check on Demand

**Create an alias** for quick checks:

```bash
# Add to your ~/.bashrc
echo 'alias bot-status="cd /home/ubuntu/folder_1/crypto-trading-bot && python3 utils/status.py"' >> ~/.bashrc
source ~/.bashrc

# Now just run:
bot-status
```

---

## 🤖 What I'll Do With The Logs

When you share logs, I will:

1. ✅ **Verify bot health** - Running, no crashes, API connection OK
2. ✅ **Check state reconciliation** - No orphan orders, positions synced
3. ✅ **Analyze signals** - How many BUY/SELL signals detected
4. ✅ **Review trades** - Entry/exit quality, stop-loss behavior
5. ✅ **Calculate performance** - Win rate, P&L, drawdown
6. ✅ **Spot issues** - Errors, warnings, unusual patterns
7. ✅ **Suggest improvements** - Strategy tweaks, risk adjustments

---

## 📊 Monitoring Schedule (Suggested)

### Daily (Quick Check)
```bash
# Takes 10 seconds
bot-status
```

If P&L looks unusual or bot stopped, share logs with me.

### Weekly (Deep Analysis)
```bash
# Generate full summary
./utils/generate_summary.sh
cat /tmp/bot_summary_*.txt
```

Share with me for performance review.

### On Alerts
If you see:
- ❌ Bot stopped
- ⚠️ Many orphan orders
- 📉 Large loss
- 🔴 Position with no stop-loss

→ Share logs immediately.

---

## 🚀 Quick Setup (Do This Now)

**Step 1: Make scripts executable**

```bash
cd /home/ubuntu/folder_1/crypto-trading-bot
chmod +x utils/generate_summary.sh
chmod +x utils/sync_to_openclaw.sh
```

**Step 2: Test it**

```bash
./utils/generate_summary.sh
```

**Step 3: Share the output with me**

```bash
cat /tmp/bot_summary_*.txt
```

Paste it in chat → I'll analyze it.

---

## 💡 Pro Tip: Set a Reminder

**On your phone/calendar:**
- Daily 9 AM: "Check trading bot" → Run `bot-status`, glance at P&L
- Sunday 6 PM: "Bot weekly review" → Generate summary, share with OpenClaw

---

## ❓ FAQ

**Q: Do I need to share logs manually every time?**  
A: Yes, for now. I can't access your machine automatically.

**Q: Can you monitor in real-time?**  
A: No, but if you share logs regularly (daily/weekly), I can track trends.

**Q: What if the bot crashes?**  
A: You'd notice it's not trading, then share logs with me to debug.

**Q: Can we automate this better?**  
A: Advanced option: Set up a webhook/API that pushes logs to me. But manual sharing works fine for most users.

---

**Ready to test?** Run this now:

```bash
cd /home/ubuntu/folder_1/crypto-trading-bot
./utils/generate_summary.sh
cat /tmp/bot_summary_*.txt
```

Then paste the output here! 📊
