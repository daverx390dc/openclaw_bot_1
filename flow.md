#  Flow of the ./start_bot.sh 
./start_bot.sh
   ↓
python3 agent.py
   ↓                (supervises & restarts)
   ├── config/api_keys.py
   ├── config/risk_params.json
   ├── logs/agent.log   (write)
   └── strategies/unified_trading_bot.py
         ↓
         ├── strategies/signal_generator.py
         ├── strategies/trailing_trade.py
         ├── ccxt (Binance API calls)
         └── logs/trades/trade_log.txt   (trade history)