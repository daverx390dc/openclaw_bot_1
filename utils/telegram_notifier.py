#!/usr/bin/env python3
"""
Telegram Notifier - Send bot alerts to Telegram
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def send_telegram_alert(message):
    """
    Send alert via OpenClaw's message tool
    Usage: python3 telegram_notifier.py "Your alert message"
    """
    # This will be called by the monitoring system
    # OpenClaw's message tool will handle sending to Telegram
    print(f"📱 TELEGRAM ALERT: {message}")
    
    # Create alert file that heartbeat monitor can pick up
    alert_file = "logs/telegram_alerts.txt"
    with open(alert_file, 'a') as f:
        from datetime import datetime, timezone
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        f.write(f"[{timestamp}] {message}\n")
    
    return message

if __name__ == "__main__":
    if len(sys.argv) > 1:
        msg = " ".join(sys.argv[1:])
        send_telegram_alert(msg)
    else:
        print("Usage: telegram_notifier.py <message>")
