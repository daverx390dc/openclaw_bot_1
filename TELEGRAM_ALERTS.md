# Telegram Alert Setup

## 🎯 What You'll Get

Automatic Telegram messages when:
- ✅ Bot crashes or stops
- ✅ First trade of the day executes
- ✅ Large profit or loss (>$20)
- ✅ Position with no stop-loss detected
- ✅ Orphan orders found
- ✅ Daily P&L summary

---

## 📱 Setup (3 Steps)

### Step 1: Find Your Telegram Bot

You already have a Telegram bot configured! To find it:

**Option A: Check bot username**
```bash
# On your Ubuntu instance, check the config
openclaw config get | grep -A5 telegram
```

**Option B: Create a new bot (if needed)**
1. Open Telegram, search for **@BotFather**
2. Send `/newbot`
3. Follow instructions
4. Copy the bot token
5. Add to OpenClaw: `openclaw configure --channel telegram`

### Step 2: Start Conversation with Your Bot

1. Open Telegram
2. Search for your bot username
3. Send `/start`
4. Send a test message: "Hi"

I should respond! 🎉

### Step 3: Tell Me You're Ready

Just send me a message on Telegram:
- "Start monitoring the trading bot"
- I'll confirm alerts are active

---

## 📊 Example Alerts You'll Receive

**Trade Executed:**
```
🚀 TRADE EXECUTED
ETH/USDT BUY @ $3,250.50
Size: 0.1538 ETH
Stop-loss: $3,220.10
Trailing: Active
```

**Daily Summary:**
```
📊 DAILY SUMMARY - 2026-02-07
Trades: 5 (3W, 2L)
Win Rate: 60%
Total P&L: +$12.50
Status: ✅ Healthy
```

**Alert:**
```
⚠️ ALERT: Position has no stop-loss!
ETH/USDT LONG @ $3,250.50
Action: Placing emergency SL
Status: Resolved ✅
```

**Bot Stopped:**
```
🔴 CRITICAL: Bot stopped
Time: 14:23 UTC
Last error: API timeout
Action: Auto-restarting...
```

---

## 🤖 How It Works

When I detect important events during my heartbeat checks, I will:
1. Detect the event (trade, error, milestone)
2. Send message to your Telegram
3. Log it for record-keeping
4. Take action if needed (auto-fix bugs)

**No configuration needed on your end** - just make sure you've started a conversation with your bot on Telegram!

---

## ✅ Verify It's Working

**Test it now:**

1. **Message your bot on Telegram:** "Test alert"
2. **I should respond immediately**
3. **Then I'll start sending bot updates automatically**

---

## 📱 Quick Commands on Telegram

Once connected, you can ask me:

- **"Bot status"** → Current health, uptime, trades
- **"Show performance"** → P&L, win rate, recent trades  
- **"Any issues?"** → Check for errors or warnings
- **"Stop alerts"** → Pause automatic notifications
- **"Resume alerts"** → Re-enable notifications

---

## 🎯 What to Do Now

**Find your Telegram bot and message it!**

If you need help finding your bot username, run:
```bash
openclaw status
```

Or just search Telegram for bots you created with @BotFather.

**Once you message me on Telegram, I'll automatically start sending bot updates there!** 📱🚀
