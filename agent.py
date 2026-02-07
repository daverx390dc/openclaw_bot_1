#!/usr/bin/env python3
"""
Autonomous Trading Agent - 24/7 Bot Manager
Monitors, restarts, and manages the crypto trading bot
"""
import asyncio
import os
import sys
import time
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Configuration
BOT_SCRIPT = "strategies/unified_trading_bot.py"
CHECK_INTERVAL = 60  # seconds between health checks
MAX_RESTARTS_PER_HOUR = 5
RESTART_COOLDOWN = 60  # seconds to wait before restart
STATE_FILE = "data/agent_state.json"
LOG_FILE = "logs/agent.log"

class TradingAgent:
    def __init__(self):
        self.process = None
        self.restart_count = 0
        self.restart_timestamps = []
        self.start_time = datetime.now(timezone.utc)
        self.last_check = None
        self.state = self.load_state()
        
    def load_state(self):
        """Load agent state from disk"""
        try:
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            self.log(f"Failed to load state: {e}")
        return {
            'total_restarts': 0,
            'last_started': None,
            'last_crash': None,
        }
    
    def save_state(self):
        """Save agent state to disk"""
        try:
            os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
            self.state['last_started'] = datetime.now(timezone.utc).isoformat()
            with open(STATE_FILE, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            self.log(f"Failed to save state: {e}")
    
    def log(self, message, level="INFO"):
        """Log message to file and console"""
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        log_line = f"[{timestamp}] [{level}] {message}\n"
        print(log_line.strip())
        
        try:
            os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
            with open(LOG_FILE, 'a') as f:
                f.write(log_line)
        except Exception as e:
            print(f"Failed to write log: {e}")
    
    def can_restart(self):
        """Check if we can restart (rate limiting)"""
        now = time.time()
        # Remove old timestamps (older than 1 hour)
        self.restart_timestamps = [ts for ts in self.restart_timestamps if now - ts < 3600]
        
        if len(self.restart_timestamps) >= MAX_RESTARTS_PER_HOUR:
            self.log(f"⛔ Restart limit reached ({MAX_RESTARTS_PER_HOUR}/hour). Waiting...", "WARNING")
            return False
        return True
    
    async def start_bot(self):
        """Start the trading bot subprocess"""
        if not self.can_restart():
            return False
        
        try:
            self.log("🚀 Starting trading bot...")
            self.process = await asyncio.create_subprocess_exec(
                sys.executable, BOT_SCRIPT,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            
            self.restart_count += 1
            self.restart_timestamps.append(time.time())
            self.state['total_restarts'] = self.state.get('total_restarts', 0) + 1
            self.save_state()
            
            # Monitor bot output in background
            asyncio.create_task(self.monitor_output())
            
            self.log(f"✅ Bot started (PID: {self.process.pid})")
            return True
            
        except Exception as e:
            self.log(f"❌ Failed to start bot: {e}", "ERROR")
            return False
    
    async def monitor_output(self):
        """Monitor bot output and log it"""
        if not self.process or not self.process.stdout:
            return
        
        try:
            async for line in self.process.stdout:
                output = line.decode().strip()
                if output:
                    # Forward bot output to agent log
                    self.log(f"[BOT] {output}")
                    
                    # Check for critical errors
                    if "ERROR" in output.upper() or "EXCEPTION" in output.upper():
                        self.log(f"⚠️ Bot error detected: {output}", "WARNING")
        except Exception as e:
            self.log(f"Output monitoring error: {e}", "ERROR")
    
    async def check_health(self):
        """Check if bot is running and healthy"""
        self.last_check = datetime.now(timezone.utc)
        
        if not self.process:
            self.log("Bot process not found", "WARNING")
            return False
        
        # Check if process is still running
        if self.process.returncode is not None:
            self.log(f"Bot exited with code {self.process.returncode}", "WARNING")
            self.state['last_crash'] = datetime.now(timezone.utc).isoformat()
            self.save_state()
            return False
        
        return True
    
    async def run(self):
        """Main agent loop"""
        self.log("═" * 60)
        self.log("AUTONOMOUS TRADING AGENT STARTED")
        self.log(f"Managing bot: {BOT_SCRIPT}")
        self.log(f"Check interval: {CHECK_INTERVAL}s")
        self.log(f"Max restarts/hour: {MAX_RESTARTS_PER_HOUR}")
        self.log("═" * 60)
        
        # Start the bot initially
        await self.start_bot()
        
        try:
            while True:
                await asyncio.sleep(CHECK_INTERVAL)
                
                is_healthy = await self.check_health()
                
                if not is_healthy:
                    self.log("🔄 Bot unhealthy, attempting restart...")
                    
                    # Cleanup old process
                    if self.process:
                        try:
                            self.process.kill()
                            await self.process.wait()
                        except:
                            pass
                    
                    # Wait before restart
                    self.log(f"Waiting {RESTART_COOLDOWN}s before restart...")
                    await asyncio.sleep(RESTART_COOLDOWN)
                    
                    # Restart
                    success = await self.start_bot()
                    if not success:
                        self.log("❌ Failed to restart bot. Waiting before retry...", "ERROR")
                        await asyncio.sleep(300)  # Wait 5 minutes
                else:
                    uptime = (datetime.now(timezone.utc) - self.start_time).total_seconds()
                    self.log(f"✓ Bot healthy | Uptime: {uptime/3600:.1f}h | Restarts: {self.restart_count}")
        
        except KeyboardInterrupt:
            self.log("🛑 Agent stopped by user")
        except Exception as e:
            self.log(f"❌ Agent error: {e}", "ERROR")
        finally:
            # Cleanup
            if self.process:
                self.log("Stopping bot...")
                try:
                    self.process.terminate()
                    await asyncio.wait_for(self.process.wait(), timeout=10)
                except:
                    self.process.kill()
                    await self.process.wait()
            
            self.log("Agent shutdown complete")


if __name__ == "__main__":
    agent = TradingAgent()
    asyncio.run(agent.run())
