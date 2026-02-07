#!/usr/bin/env python3
"""
Signal Monitor - Tracks signal detection vs order placement
Created by OpenClaw AI on 2026-02-07 to prove modification capability
"""
import os
import time
from datetime import datetime, timezone

STATE_LOG = "logs/state_debug.log"
SIGNAL_TRACKING = "logs/signal_tracking.txt"

def monitor_signals():
    """Monitor state_debug.log for signal → order flow"""
    print(f"Monitoring signals in: {STATE_LOG}")
    print(f"Tracking file: {SIGNAL_TRACKING}")
    
    signals = []
    orders = []
    
    if os.path.exists(STATE_LOG):
        with open(STATE_LOG, 'r') as f:
            for line in f:
                if 'signal detected' in line.lower():
                    signals.append(line.strip())
                if 'ENTRY FILLED' in line or 'Entry order filled' in line:
                    orders.append(line.strip())
    
    # Write tracking summary
    with open(SIGNAL_TRACKING, 'w') as f:
        f.write("="*70 + "\n")
        f.write("SIGNAL → ORDER TRACKING\n")
        f.write(f"Updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
        f.write("="*70 + "\n\n")
        
        f.write(f"📊 Signals Detected: {len(signals)}\n")
        f.write(f"✅ Orders Placed: {len(orders)}\n")
        
        if len(signals) > 0:
            success_rate = (len(orders) / len(signals)) * 100
            f.write(f"🎯 Success Rate: {success_rate:.1f}%\n\n")
            
            if success_rate < 95:
                f.write("⚠️ WARNING: Signal-to-order success rate below 95%!\n\n")
        
        if signals:
            f.write("Recent Signals:\n")
            for sig in signals[-5:]:
                f.write(f"  {sig}\n")
        else:
            f.write("No signals detected yet - waiting for market conditions...\n")
    
    print(f"✅ Created tracking file: {SIGNAL_TRACKING}")
    print(f"   Signals: {len(signals)} | Orders: {len(orders)}")

if __name__ == "__main__":
    monitor_signals()
