async def verify_no_position():
    """Verify we have no position on exchange"""
    try:
        positions = await exchange.fetch_positions([SYMBOL])
        active = next((p for p in positions if float(p.get('contracts', p.get('positionAmt', 0))) != 0), None)
        if active:
            amt = float(active.get('contracts', active.get('positionAmt', 0)))
            log_state(f"Position check: FOUND {amt}")
            return False
        log_state("Position check: CLEAR")
        return True
    except Exception as e:
        log_state(f"Position check error: {e}")
        return True


def get_atr_from_df(df):
    """Get ATR from dataframe"""
    if len(df) < 30 or 'atr' not in df.columns:
        return None
    atr = df['atr'].iloc[-1]
    return None if pd.isna(atr) else float(atr)


# ════════════════════════════════════════════════════════════════════════════
# POSITION ENTRY (IMPROVED)
# ════════════════════════════════════════════════════════════════════════════
async def place_entry(side: str, signal_price: float, atr: float):
    global current_position, stop_order_id
    
    log_state(f"=== ENTRY ATTEMPT: {side} @ {signal_price:.2f} ===")
    
    # SAFETY CHECK 1: Verify no existing position
    has_no_position = await verify_no_position()
    if not has_no_position:
        print(f"❌ ENTRY BLOCKED: Exchange shows active position!")
        log_state("ENTRY BLOCKED: Position already exists")
        return
    
    # SAFETY CHECK 2: Cancel any orphan orders first
    await cancel_all_orders()
    await asyncio.sleep(0.5)
    
    risk_dist = INITIAL_SL_MULT * atr
    qty_raw = (POSITION_SIZE_USDT / signal_price) * LEVERAGE
    qty = exchange.amount_to_precision(SYMBOL, qty_raw)

    print(f"ENTRY → {side} | Price: {signal_price:.2f} | ATR: {atr:.2f} | Qty: {qty}")
    log_state(f"Entry params: side={side}, qty={qty}, risk_dist={risk_dist:.2f}")
    
    side_str = 'buy' if side == 'BUY' else 'sell'

    try:
        # Place market order
        order = await exchange.create_market_order(SYMBOL, side_str, qty)
        print(f"✅ ENTRY FILLED: {order.get('id')}")
        log_state(f"Entry order filled: {order}")
        
        entry_price = float(order.get('average') or order.get('price') or signal_price)
        notional = entry_price * float(qty)

        sl_price = entry_price - risk_dist if side == 'BUY' else entry_price + risk_dist

        current_position = {
            'side': 'long' if side == 'BUY' else 'short',
            'entry_price': entry_price,
            'quantity': float(qty),
            'initial_risk': risk_dist,
            'sl_price': sl_price,
            'breakeven_triggered': False,
            'trailing_active': False,
            'trail_distance': 0.0,
            'entry_notional': notional,
            'entry_time': datetime.now(timezone.utc),
        }
        
        log_state(f"Position created: {current_position}")

        # Place stop-loss with RETRY LOGIC
        sl_side = 'sell' if side == 'BUY' else 'buy'
        sl_placed = False
        
        for attempt in range(3):
            try:
                log_state(f"SL placement attempt {attempt+1}/3: price={sl_price:.2f}, side={sl_side}, qty={qty}")
                
                # STOP_MARKET order: executes at market price when stopPrice is hit
                sl_order = await exchange.create_order(
                    SYMBOL, 'STOP_MARKET', sl_side, qty, None,
                    {'stopPrice': sl_price, 'reduceOnly': True}
                )
                stop_order_id = sl_order['id']
                order_history[stop_order_id] = time.time()  # Track order timestamp
                print(f"✅ Initial SL placed @ {sl_price:.2f} (ID: {stop_order_id})")
                log_state(f"SL order placed: {stop_order_id} @ {sl_price:.2f}")
                
                # VERIFY the stop order was actually placed
                await asyncio.sleep(0.5)
                orders = await exchange.fetch_open_orders(SYMBOL)
                sl_exists = any(o['id'] == stop_order_id for o in orders)
                if sl_exists:
                    log_state(f"✅ SL verified in open orders")
                    sl_placed = True
                    break
                else:
                    log_state(f"⚠️ SL created but not verified (attempt {attempt+1})")
                    if attempt < 2:
                        await asyncio.sleep(1)
            
            except Exception as e:
                log_state(f"SL attempt {attempt+1} failed: {type(e).__name__}: {e}")
                print(f"⚠️ SL placement attempt {attempt+1} failed: {e}")
                if attempt < 2:
                    await asyncio.sleep(1)
        
        if not sl_placed:
            log_state(f"CRITICAL: SL placement failed after 3 attempts - POSITION UNPROTECTED!")
            print(f"❌ CRITICAL: Failed to place stop-loss after 3 attempts!")
            print(f"⚠️ Position is UNPROTECTED - IMMEDIATE MANUAL INTERVENTION REQUIRED!")

        # Log entry
        log_trade(side, entry_price, None, float(qty), "ENTRY")

    except Exception as e:
        log_state(f"Entry failed: {e}")
        print(f"❌ Entry failed: {type(e).__name__} → {e}")

