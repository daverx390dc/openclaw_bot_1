#!/usr/bin/env python3
"""
Quick status checker for the trading bot
Shows: uptime, restarts, recent trades, current P&L
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

def load_json(path):
    try:
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
    except:
        pass
    return {}

def get_agent_status():
    """Get agent state"""
    state = load_json('data/agent_state.json')
    if not state:
        return "Agent not started yet"
    
    last_started = state.get('last_started')
    if last_started:
        started_dt = datetime.fromisoformat(last_started.replace('Z', '+00:00'))
        uptime = (datetime.now(timezone.utc) - started_dt).total_seconds() / 3600
        return f"Uptime: {uptime:.1f}h | Restarts: {state.get('total_restarts', 0)}"
    return "Unknown"

def get_recent_trades(n=5):
    """Get last N trades"""
    log_file = 'logs/trades/trade_log.txt'
    if not os.path.exists(log_file):
        return []
    
    with open(log_file, 'r') as f:
        lines = f.readlines()
    
    # Skip header
    trades = [line.strip() for line in lines[1:] if line.strip()]
    return trades[-n:]

def calculate_total_pnl():
    """Calculate total P&L from trade log"""
    log_file = 'logs/trades/trade_log.txt'
    if not os.path.exists(log_file):
        return 0.0
    
    total_pnl = 0.0
    with open(log_file, 'r') as f:
        for line in f:
            if 'PNL:' in line:
                try:
                    # Extract PNL value
                    pnl_part = line.split('PNL:')[1].split('USDT')[0].strip()
                    total_pnl += float(pnl_part)
                except:
                    pass
    
    return total_pnl

def main():
    print("=" * 60)
    print("CRYPTO TRADING BOT STATUS")
    print("=" * 60)
    print()
    
    # Agent status
    print(f"Agent: {get_agent_status()}")
    print()
    
    # Total P&L
    total_pnl = calculate_total_pnl()
    pnl_sign = "+" if total_pnl >= 0 else ""
    print(f"Total P&L: {pnl_sign}{total_pnl:.2f} USDT")
    print()
    
    # Recent trades
    print("Recent Trades:")
    print("-" * 60)
    trades = get_recent_trades(5)
    if trades:
        for trade in trades:
            print(trade)
    else:
        print("No trades yet")
    print()
    
    print("=" * 60)
    print("Run 'tail -f logs/agent.log' to monitor live")
    print("=" * 60)

if __name__ == "__main__":
    main()
