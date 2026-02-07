#!/usr/bin/env python3
"""
Performance Tracker - Continuously updates trading performance summary
Monitors trade_log.txt and generates live performance dashboard
"""
import os
import time
from datetime import datetime, timezone

TRADE_LOG = "logs/trades/trade_log.txt"
PERFORMANCE_FILE = "LIVE_PERFORMANCE.txt"
UPDATE_INTERVAL = 10  # seconds

def parse_trade_log():
    """Parse trade_log.txt and extract all trades"""
    if not os.path.exists(TRADE_LOG):
        return []
    
    trades = []
    with open(TRADE_LOG, 'r') as f:
        lines = f.readlines()
    
    # Skip header
    for line in lines[1:]:
        if not line.strip():
            continue
        
        try:
            parts = line.split('|')
            if len(parts) < 7:
                continue
            
            timestamp = parts[0].strip()
            side = parts[1].strip().replace('Side:', '').strip()
            entry = parts[2].strip().replace('Entry:', '').strip()
            exit_price = parts[3].strip().replace('Exit:', '').strip()
            qty = parts[4].strip().replace('Qty:', '').strip()
            pnl_part = parts[5].strip().replace('PNL:', '').strip()
            reason = parts[6].strip().replace('Reason:', '').strip()
            
            # Extract PNL value (format: "+12.50 USDT (+1.23%)")
            if 'USDT' in pnl_part:
                pnl_usdt = float(pnl_part.split('USDT')[0].strip())
                pnl_pct = pnl_part.split('(')[1].split('%')[0].strip() if '(' in pnl_part else '0.0'
            else:
                pnl_usdt = 0.0
                pnl_pct = '0.0'
            
            # Only count EXIT trades (not ENTRY)
            if exit_price != 'N/A' and reason != 'ENTRY':
                trades.append({
                    'timestamp': timestamp,
                    'side': side,
                    'entry': entry,
                    'exit': exit_price,
                    'qty': qty,
                    'pnl_usdt': pnl_usdt,
                    'pnl_pct': float(pnl_pct),
                    'reason': reason
                })
        except Exception as e:
            # Skip malformed lines
            continue
    
    return trades


def calculate_performance(trades):
    """Calculate performance metrics"""
    if not trades:
        return {
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'win_rate': 0.0,
            'total_pnl': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'largest_win': 0.0,
            'largest_loss': 0.0,
            'profit_factor': 0.0
        }
    
    total_trades = len(trades)
    wins = [t for t in trades if t['pnl_usdt'] > 0]
    losses = [t for t in trades if t['pnl_usdt'] < 0]
    
    win_count = len(wins)
    loss_count = len(losses)
    win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0.0
    
    total_pnl = sum(t['pnl_usdt'] for t in trades)
    
    avg_win = sum(t['pnl_usdt'] for t in wins) / win_count if win_count > 0 else 0.0
    avg_loss = sum(t['pnl_usdt'] for t in losses) / loss_count if loss_count > 0 else 0.0
    
    largest_win = max((t['pnl_usdt'] for t in wins), default=0.0)
    largest_loss = min((t['pnl_usdt'] for t in losses), default=0.0)
    
    total_wins = sum(t['pnl_usdt'] for t in wins)
    total_losses = abs(sum(t['pnl_usdt'] for t in losses))
    profit_factor = total_wins / total_losses if total_losses > 0 else 0.0
    
    return {
        'total_trades': total_trades,
        'wins': win_count,
        'losses': loss_count,
        'win_rate': win_rate,
        'total_pnl': total_pnl,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'largest_win': largest_win,
        'largest_loss': largest_loss,
        'profit_factor': profit_factor,
        'last_trades': trades[-5:]  # Last 5 trades
    }


def generate_dashboard(stats):
    """Generate performance dashboard text"""
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    
    pnl_sign = '+' if stats['total_pnl'] >= 0 else ''
    pnl_emoji = '🟢' if stats['total_pnl'] > 0 else '🔴' if stats['total_pnl'] < 0 else '⚪'
    
    dashboard = f"""
{'='*70}
            CRYPTO TRADING BOT - LIVE PERFORMANCE
{'='*70}
Last Updated: {now}

📊 OVERALL PERFORMANCE
{'─'*70}
Total Trades:        {stats['total_trades']}
Wins:                {stats['wins']} ✅
Losses:              {stats['losses']} ❌
Win Rate:            {stats['win_rate']:.1f}%

💰 PROFIT & LOSS
{'─'*70}
Total P&L:           {pnl_emoji} {pnl_sign}${stats['total_pnl']:.2f} USDT

Average Win:         +${stats['avg_win']:.2f}
Average Loss:        ${stats['avg_loss']:.2f}
Largest Win:         +${stats['largest_win']:.2f}
Largest Loss:        ${stats['largest_loss']:.2f}

Profit Factor:       {stats['profit_factor']:.2f}x
"""

    if stats['last_trades']:
        dashboard += f"\n📈 RECENT TRADES (Last 5)\n{'─'*70}\n"
        for i, trade in enumerate(reversed(stats['last_trades']), 1):
            pnl_sign = '+' if trade['pnl_usdt'] >= 0 else ''
            emoji = '✅' if trade['pnl_usdt'] > 0 else '❌'
            dashboard += f"{i}. {trade['timestamp'][:19]} | {trade['side']:4} | "
            dashboard += f"Entry: {trade['entry']:8} | Exit: {trade['exit']:8} | "
            dashboard += f"P&L: {pnl_sign}${trade['pnl_usdt']:6.2f} {emoji}\n"
    else:
        dashboard += f"\n📈 RECENT TRADES\n{'─'*70}\n"
        dashboard += "No trades yet - waiting for signals...\n"
    
    dashboard += f"\n{'='*70}\n"
    dashboard += "💡 TIP: Check your Binance testnet account balance to verify!\n"
    dashboard += "    https://testnet.binancefuture.com/\n"
    dashboard += f"{'='*70}\n"
    
    return dashboard


def main():
    """Main monitoring loop"""
    print("Starting performance tracker...")
    print(f"Monitoring: {TRADE_LOG}")
    print(f"Output: {PERFORMANCE_FILE}")
    print(f"Update interval: {UPDATE_INTERVAL}s")
    print("Press Ctrl+C to stop\n")
    
    while True:
        try:
            # Parse trades
            trades = parse_trade_log()
            
            # Calculate stats
            stats = calculate_performance(trades)
            
            # Generate dashboard
            dashboard = generate_dashboard(stats)
            
            # Write to file
            with open(PERFORMANCE_FILE, 'w') as f:
                f.write(dashboard)
            
            # Print summary
            pnl_sign = '+' if stats['total_pnl'] >= 0 else ''
            print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] "
                  f"Trades: {stats['total_trades']} | "
                  f"P&L: {pnl_sign}${stats['total_pnl']:.2f} | "
                  f"Win Rate: {stats['win_rate']:.1f}%")
            
            time.sleep(UPDATE_INTERVAL)
            
        except KeyboardInterrupt:
            print("\n\nStopped by user.")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(UPDATE_INTERVAL)


if __name__ == "__main__":
    main()
