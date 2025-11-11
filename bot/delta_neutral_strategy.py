"""
Delta Neutral Trading Strategy
Automatically opens and closes hedged positions on Paradex (long) and Lighter (short)
"""

import asyncio
import random
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from .trading_bot import TradingBot
from .notifier import DiscordNotifier


class DeltaNeutralStrategy:
    """Delta neutral strategy with automatic position rotation"""

    POSITION_FILE = ".current_position.json"
    HISTORY_FILE = ".history.json"

    def __init__(self, bot: TradingBot, leverage: int = 10, capital_percentage: float = 0.5, usd_amount: float = None):
        """
        Initialize delta neutral strategy

        Args:
            bot: TradingBot instance
            leverage: Leverage multiplier (default: 10x)
            capital_percentage: Percentage of capital to use (default: 0.5 = 50%)
            usd_amount: Fixed USD amount to use per position (overrides balance-based calculation)
        """
        self.bot = bot
        self.leverage = leverage
        self.capital_percentage = capital_percentage
        self.usd_amount = usd_amount
        self.position_open = False
        self.current_position = None
        self.notifier = DiscordNotifier()

    async def _determine_optimal_position_direction(self) -> Dict[str, str]:
        """
        Determine optimal position direction based on funding rates

        Returns:
            Dictionary with 'paradex' and 'lighter' sides ('LONG' or 'SHORT')
            Example: {'paradex': 'LONG', 'lighter': 'SHORT'}
        """
        print(f"\n💰 Funding Rate Check...")

        # Get funding rates from both exchanges
        paradex_funding = await self.bot.paradex.get_funding_rate()
        lighter_funding = await self.bot.lighter.get_funding_rate()

        print(f"   Paradex: {paradex_funding*100:.4f}% / 8h" if paradex_funding is not None else "   Paradex: N/A")
        print(f"   Lighter: {lighter_funding*100:.4f}% / 8h" if lighter_funding is not None else "   Lighter: N/A")

        # If we can't get funding rates, use default (Paradex LONG + Lighter SHORT)
        if paradex_funding is None or lighter_funding is None:
            print(f"   ⚠️  Using default strategy (Paradex LONG + Lighter SHORT)")
            return {'paradex': 'LONG', 'lighter': 'SHORT'}

        # Calculate net funding cost for both combinations
        # Option A: Paradex LONG + Lighter SHORT
        option_a_cost = paradex_funding - lighter_funding
        # Option B: Paradex SHORT + Lighter LONG
        option_b_cost = -paradex_funding + lighter_funding

        # Choose the option with lower cost (more negative = better)
        if option_a_cost <= option_b_cost:
            print(f"   ✅ Strategy: Paradex LONG + Lighter SHORT (cost: {option_a_cost*100:.4f}% / 8h)")
            return {'paradex': 'LONG', 'lighter': 'SHORT'}
        else:
            print(f"   ✅ Strategy: Paradex SHORT + Lighter LONG (cost: {option_b_cost*100:.4f}% / 8h)")
            return {'paradex': 'SHORT', 'lighter': 'LONG'}

    async def _wait_for_tight_spread(self, max_spread_pct: float, check_interval: float, timeout: float) -> Optional[tuple]:
        """
        Wait for bid-ask spread on EACH exchange to be within acceptable range

        Args:
            max_spread_pct: Maximum allowed spread in percentage (e.g., 0.02 for 0.02%)
            check_interval: How often to check prices in seconds
            timeout: How long to wait before giving up (0 = infinite)

        Returns:
            Tuple of (paradex_mid_price, lighter_mid_price) if condition met, None if timeout
        """
        print(f"\n⏳ 各取引所のbid-askスプレッドを監視中... (≤ {max_spread_pct}%)")
        print(f"   チェック間隔: {check_interval}秒")
        print(f"   タイムアウト: {'∞ (無限)' if timeout == 0 else f'{timeout}秒'}")

        start_time = datetime.now()
        check_count = 0

        while True:
            check_count += 1

            # Get bid/ask prices from both exchanges
            paradex_bid_ask = await self.bot.paradex.get_bid_ask()
            lighter_bid_ask = await self.bot.lighter.get_bid_ask()

            if not paradex_bid_ask or not lighter_bid_ask:
                print(f"\r   [{check_count}] ❌ 価格取得失敗、リトライ中...", end='', flush=True)
                await asyncio.sleep(check_interval)
                continue

            # Extract bid/ask
            paradex_bid, paradex_ask = paradex_bid_ask
            lighter_bid, lighter_ask = lighter_bid_ask

            # Calculate mid prices
            paradex_mid = (paradex_bid + paradex_ask) / 2
            lighter_mid = (lighter_bid + lighter_ask) / 2

            # Calculate bid-ask spread for each exchange
            paradex_spread = abs(paradex_ask - paradex_bid)
            paradex_spread_pct = (paradex_spread / paradex_mid) * 100

            lighter_spread = abs(lighter_ask - lighter_bid)
            lighter_spread_pct = (lighter_spread / lighter_mid) * 100

            # Display current status
            elapsed = (datetime.now() - start_time).total_seconds()
            print(f"\r   [{check_count}] Paradex: {paradex_spread_pct:.4f}% | Lighter: {lighter_spread_pct:.4f}% | 経過: {elapsed:.0f}秒", end='', flush=True)

            # Check if BOTH spreads are acceptable
            if paradex_spread_pct <= max_spread_pct and lighter_spread_pct <= max_spread_pct:
                print(f"\n✅ スプレッド条件達成!")
                print(f"   Paradex: {paradex_spread_pct:.4f}% (Bid: ${paradex_bid:.4f}, Ask: ${paradex_ask:.4f})")
                print(f"   Lighter: {lighter_spread_pct:.4f}% (Bid: ${lighter_bid:.4f}, Ask: ${lighter_ask:.4f})")
                return (paradex_mid, lighter_mid)

            # Check timeout (if not infinite)
            if timeout > 0:
                if elapsed >= timeout:
                    print(f"\n⏰ タイムアウト到達 ({elapsed:.0f}秒)")
                    print(f"   Paradex: {paradex_spread_pct:.4f}% | Lighter: {lighter_spread_pct:.4f}%")
                    print(f"   目標: ≤{max_spread_pct}%")
                    return None

            # Wait before next check
            await asyncio.sleep(check_interval)

    def _save_position_to_file(self):
        """Save current position to file for emergency close"""
        try:
            with open(self.POSITION_FILE, 'w') as f:
                json.dump(self.current_position, f, indent=2)
        except Exception as e:
            print(f"⚠️  Failed to save position to file: {e}")

    def _remove_position_file(self):
        """Remove position file after closing"""
        try:
            if os.path.exists(self.POSITION_FILE):
                os.remove(self.POSITION_FILE)
        except Exception as e:
            print(f"⚠️  Failed to remove position file: {e}")

    def _save_to_history(self, trade_data: Dict[str, Any]):
        """Save completed trade to history file"""
        try:
            # Load existing history
            history = []
            if os.path.exists(self.HISTORY_FILE):
                with open(self.HISTORY_FILE, 'r') as f:
                    history = json.load(f)

            # Append new trade
            history.append(trade_data)

            # Save updated history
            with open(self.HISTORY_FILE, 'w') as f:
                json.dump(history, f, indent=2)

            print(f"📝 Trade saved to history ({len(history)} total trades)")
        except Exception as e:
            print(f"⚠️  Failed to save trade to history: {e}")

    @staticmethod
    def load_current_position() -> Optional[Dict[str, Any]]:
        """Load current position from file"""
        try:
            if os.path.exists(DeltaNeutralStrategy.POSITION_FILE):
                with open(DeltaNeutralStrategy.POSITION_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"⚠️  Failed to load position from file: {e}")
        return None

    async def get_available_balance(self) -> Dict[str, float]:
        """
        Get available balances from both exchanges

        Returns:
            Dictionary with balances for each exchange
        """
        print("\n💰 Checking available balances...")

        # Get balance from both exchanges
        paradex_balance_info = await self.bot.paradex.get_account_balance()
        lighter_balance_info = await self.bot.lighter.get_account_balance()

        # Extract USDC balance (assuming USDC as collateral)
        paradex_balance = 0.0
        lighter_balance = 0.0

        if paradex_balance_info:
            # Extract balance from Paradex response
            # Paradex returns AccountSummary object with attributes
            if hasattr(paradex_balance_info, 'total_collateral'):
                # SDK response (AccountSummary object)
                paradex_balance = float(paradex_balance_info.total_collateral or 0)
            elif hasattr(paradex_balance_info, 'free_collateral'):
                paradex_balance = float(paradex_balance_info.free_collateral or 0)
            elif isinstance(paradex_balance_info, dict):
                # REST API response (dict)
                paradex_balance = float(paradex_balance_info.get('total_collateral', 0) or
                                      paradex_balance_info.get('free_collateral', 0) or
                                      paradex_balance_info.get('available_balance', 0) or 0)

        if lighter_balance_info:
            # Extract balance from Lighter response
            if isinstance(lighter_balance_info, dict):
                # Lighter API response has 'accounts' array
                if 'accounts' in lighter_balance_info and len(lighter_balance_info['accounts']) > 0:
                    account = lighter_balance_info['accounts'][0]
                    lighter_balance = float(account.get('total_asset_value', 0) or
                                          account.get('available_balance', 0) or
                                          account.get('collateral', 0) or 0)
                else:
                    # Direct balance keys
                    lighter_balance = float(lighter_balance_info.get('total_asset_value', 0) or
                                          lighter_balance_info.get('available_balance', 0) or
                                          lighter_balance_info.get('equity', 0) or
                                          lighter_balance_info.get('balance', 0) or 0)

        balances = {
            'paradex': paradex_balance,
            'lighter': lighter_balance
        }

        print(f"   Paradex: ${paradex_balance:.2f}")
        print(f"   Lighter: ${lighter_balance:.2f}")

        return balances

    async def _place_lighter_limit_with_price_update(self, size: float, max_attempts: int = 12, wait_seconds: int = 5) -> Optional[Dict[str, Any]]:
        """
        Place Lighter limit order with price updates until filled

        Args:
            size: Order size
            max_attempts: Maximum number of attempts (default: 12)
            wait_seconds: Seconds to wait between attempts (default: 5)

        Returns:
            Order result if filled, None if failed
        """
        print(f"\n📍 Lighter指値注文（価格自動更新）")
        print(f"   目標サイズ: {size:.2f}")
        print(f"   最大試行回数: {max_attempts}")
        print(f"   更新間隔: {wait_seconds}秒")

        current_order_id = None

        for attempt in range(1, max_attempts + 1):
            print(f"\n{'='*60}")
            print(f"🔄 試行 {attempt}/{max_attempts}")
            print(f"{'='*60}")

            # Get latest bid/ask
            bid_ask = await self.bot.lighter.get_bid_ask()
            if not bid_ask:
                print("❌ 価格取得失敗")
                await asyncio.sleep(wait_seconds)
                continue

            best_bid, best_ask = bid_ask

            # Use best ask for SELL limit order (most likely to fill)
            limit_price = best_ask

            print(f"   最新価格: Bid ${best_bid:.4f} | Ask ${best_ask:.4f}")
            print(f"   指値価格: ${limit_price:.4f} (Best Ask)")

            # Cancel previous order if exists
            if current_order_id:
                print(f"   🗑️  前回の注文をキャンセル中...")
                await self.bot.lighter.cancel_order(str(current_order_id))

            # Place new limit order
            order_result = await self.bot.lighter.place_limit_order('SELL', size, limit_price)

            if not order_result:
                print("❌ 注文失敗")
                await asyncio.sleep(wait_seconds)
                continue

            current_order_id = order_result.get('order_id')
            tx_hash = order_result.get('tx_hash')

            print(f"   ✓ 注文送信完了")
            print(f"   Order ID: {current_order_id}")
            print(f"   TX Hash: {tx_hash}")

            # Wait and check if filled
            print(f"   ⏳ {wait_seconds}秒待機中...")
            await asyncio.sleep(wait_seconds)

            # Check order status
            # Note: For Lighter, if tx succeeded, we assume it's filled
            # In a production environment, you'd query the order status from the API
            if tx_hash:
                print(f"   ✅ 注文約定完了！")
                return {
                    **order_result,
                    'filled_size': size,
                    'filled_price': limit_price,
                    'status': 'FILLED'
                }

            print(f"   ⚠️  約定未確認 - 価格を更新して再試行...")

        # Max attempts reached
        print(f"\n❌ 最大試行回数到達 - Lighter注文失敗")
        if current_order_id:
            print(f"   最終注文をキャンセル中...")
            await self.bot.lighter.cancel_order(str(current_order_id))

        return None

    async def _verify_filled_size(self, order_result: Any, expected_size: float, exchange_name: str) -> float:
        """
        Verify the actual filled size from order result

        Args:
            order_result: Order result from exchange
            expected_size: Expected position size
            exchange_name: Name of exchange for logging

        Returns:
            Actual filled size (returns expected_size if verification fails)
        """
        try:
            # For now, assume full fill if order succeeded
            # In production, you'd parse the order result to get actual fill
            # This is a placeholder - actual implementation depends on exchange API response
            if order_result:
                # TODO: Parse actual filled size from order_result
                # For Paradex SDK: order_result might have 'filled_qty' or 'size'
                # For Lighter SDK: order_result might have different structure
                return expected_size
            return 0.0
        except Exception as e:
            print(f"⚠️  Failed to verify fill size for {exchange_name}: {e}")
            return expected_size  # Assume full fill if we can't verify

    async def _fill_shortage(self, paradex_shortage: float, lighter_shortage: float,
                            paradex_price: float, lighter_price: float) -> tuple:
        """
        Fill position shortage by placing additional orders

        Args:
            paradex_shortage: Shortage on Paradex
            lighter_shortage: Shortage on Lighter
            paradex_price: Current Paradex price
            lighter_price: Current Lighter price

        Returns:
            Tuple of (paradex_filled, lighter_filled)
        """
        print(f"\n🔄 Filling shortage...")
        print(f"   Paradex: {paradex_shortage:.2f} units")
        print(f"   Lighter: {lighter_shortage:.2f} units")

        tasks = []
        if paradex_shortage > 0:
            tasks.append(self.bot.paradex.place_market_order('BUY', paradex_shortage))
        else:
            tasks.append(None)

        if lighter_shortage > 0:
            tasks.append(self.bot.lighter.place_market_order('SELL', lighter_shortage))
        else:
            tasks.append(None)

        # Execute shortage fills
        results = []
        for task in tasks:
            if task is None:
                results.append(None)
            else:
                results.append(await task)

        paradex_result, lighter_result = results

        # Verify fills
        paradex_filled = await self._verify_filled_size(paradex_result, paradex_shortage, "Paradex") if paradex_shortage > 0 else 0
        lighter_filled = await self._verify_filled_size(lighter_result, lighter_shortage, "Lighter") if lighter_shortage > 0 else 0

        print(f"   ✓ Paradex filled: {paradex_filled:.2f}")
        print(f"   ✓ Lighter filled: {lighter_filled:.2f}")

        return (paradex_filled, lighter_filled)

    async def _emergency_close_all(self, paradex_size: float, lighter_size: float = None) -> bool:
        """
        Emergency close all positions and reset

        Args:
            paradex_size: Size of Paradex position to close
            lighter_size: Size of Lighter position to close (defaults to paradex_size if not provided)

        Returns:
            True if successfully closed
        """
        # For backward compatibility, if lighter_size not provided, use paradex_size
        if lighter_size is None:
            lighter_size = paradex_size

        # Get position sides if available
        paradex_side = self.current_position.get('paradex_side', 'LONG') if self.current_position else 'LONG'
        lighter_side = self.current_position.get('lighter_side', 'SHORT') if self.current_position else 'SHORT'

        # Determine close sides
        paradex_close_side = 'SELL' if paradex_side == 'LONG' else 'BUY'
        lighter_close_side = 'SELL' if lighter_side == 'LONG' else 'BUY'

        print("\n🚨 EMERGENCY: Closing all positions...")
        print(f"   Paradex: {paradex_close_side} {paradex_size:.2f} units (Close {paradex_side})")
        print(f"   Lighter: {lighter_close_side} {lighter_size:.2f} units (Close {lighter_side})")

        try:
            # Close both positions with independent sizes
            tasks = [
                self.bot.paradex.place_market_order(paradex_close_side, paradex_size),
                self.bot.lighter.place_market_order(lighter_close_side, lighter_size)
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            paradex_result = results[0]
            lighter_result = results[1]

            paradex_success = not isinstance(paradex_result, Exception) and paradex_result
            lighter_success = not isinstance(lighter_result, Exception) and lighter_result

            if paradex_success and lighter_success:
                print("✅ All positions closed successfully")
                # Send notification
                await self.notifier.send_error(
                    "Emergency closure completed",
                    f"Closed Paradex: {paradex_size:.2f}, Lighter: {lighter_size:.2f} after retry failure"
                )
                return True
            else:
                print("❌ Failed to close some positions")
                if not paradex_success:
                    print(f"   Paradex error: {paradex_result}")
                if not lighter_success:
                    print(f"   Lighter error: {lighter_result}")

                # Send critical alert
                await self.notifier.send_error(
                    "CRITICAL: Emergency closure failed",
                    "MANUAL INTERVENTION REQUIRED - Check open positions!"
                )
                return False

        except Exception as e:
            print(f"❌ Emergency close error: {e}")
            await self.notifier.send_error(
                f"CRITICAL: Emergency close exception: {e}",
                "MANUAL INTERVENTION REQUIRED"
            )
            return False

    async def calculate_position_size(self, price: float, balance: float) -> float:
        """
        Calculate position size based on leverage and capital percentage

        Args:
            price: Current asset price
            balance: Available balance in USD

        Returns:
            Position size in base asset units
        """
        # Use 50% of balance with 10x leverage
        usable_capital = balance * self.capital_percentage
        total_buying_power = usable_capital * self.leverage
        position_size = total_buying_power / price

        print(f"   Balance: ${balance:.2f}")
        print(f"   Using {self.capital_percentage*100}% = ${usable_capital:.2f}")
        print(f"   With {self.leverage}x leverage = ${total_buying_power:.2f}")
        print(f"   Position size: {position_size:.2f} units @ ${price:.4f}")

        return position_size

    async def open_delta_neutral_position(self) -> Dict[str, Any]:
        """
        Open delta neutral position:
        - Paradex: LONG (BUY)
        - Lighter: SHORT (SELL)

        Returns:
            Results of position opening
        """
        print("\n" + "="*60)
        print("🎯 Opening Delta Neutral Position")
        print("="*60)

        # Get and display current balances
        balances = await self.get_available_balance()
        paradex_balance = balances.get('paradex', 0)
        lighter_balance = balances.get('lighter', 0)

        # Get spread monitoring configuration
        max_spread_pct = self.bot.config.spread_max_pct
        check_interval = self.bot.config.spread_check_interval
        timeout = self.bot.config.spread_check_timeout

        # Wait for tight spread
        price_result = await self._wait_for_tight_spread(max_spread_pct, check_interval, timeout)

        if price_result is None:
            print("❌ Failed to achieve target spread within timeout")
            return {'success': False, 'error': 'Spread timeout'}

        paradex_price, lighter_price = price_result

        if not paradex_price or not lighter_price:
            print("❌ Failed to get prices")
            return {'success': False, 'error': 'Price fetch failed'}

        avg_price = (paradex_price + lighter_price) / 2

        # Determine optimal position direction based on funding rates
        position_direction = await self._determine_optimal_position_direction()
        paradex_side = position_direction['paradex']  # 'LONG' or 'SHORT'
        lighter_side = position_direction['lighter']  # 'LONG' or 'SHORT'

        # Calculate position size
        if self.usd_amount:
            # Calculate INDEPENDENT position size for each exchange to match USD amount
            # This ensures each exchange gets as close to the target USD amount as possible
            paradex_target_size = int(self.usd_amount / paradex_price)
            lighter_target_size = int(self.usd_amount / lighter_price)

            # Calculate actual USD amounts with independent sizes
            paradex_usd = paradex_target_size * paradex_price
            lighter_usd = lighter_target_size * lighter_price

            print(f"\n💵 Using fixed USD amount: ${self.usd_amount:.2f}")
            print(f"   Paradex: {paradex_target_size} units @ ${paradex_price:.4f} = ${paradex_usd:.2f}")
            print(f"   Lighter: {lighter_target_size} units @ ${lighter_price:.4f} = ${lighter_usd:.2f}")

            # Use independent sizes for more accurate USD matching
            paradex_position_size = paradex_target_size
            lighter_position_size = lighter_target_size
            position_size = paradex_target_size  # For display purposes
        else:
            # Get balances
            balances = await self.get_available_balance()

            # Calculate position size based on available balance
            # Use the smaller balance to ensure both sides can be filled
            available_balance = min(balances['paradex'], balances['lighter'])

            if available_balance <= 0:
                print("❌ No available balance detected")
                print("⚠️  Falling back to test mode with 1.0 unit")
                position_size = 1.0
                paradex_position_size = position_size
                lighter_position_size = position_size
            else:
                position_size = await self.calculate_position_size(avg_price, available_balance)
                # Round down to integer
                position_size = int(position_size)
                # Use same size for both when balance-based
                paradex_position_size = position_size
                lighter_position_size = position_size

        # Convert LONG/SHORT to BUY/SELL
        paradex_order_side = 'BUY' if paradex_side == 'LONG' else 'SELL'
        lighter_order_side = 'BUY' if lighter_side == 'LONG' else 'SELL'

        print(f"\n📊 Opening: Lighter {lighter_order_side} {lighter_position_size} → Paradex {paradex_order_side} {paradex_position_size}")
        print(f"   Prices: Paradex ${paradex_price:.4f} | Lighter ${lighter_price:.4f}")

        # Get Lighter order configuration
        lighter_spread_max = self.bot.config.lighter_spread_max_pct
        lighter_timeout = self.bot.config.lighter_order_timeout
        use_websocket = self.bot.config.lighter_use_websocket

        # STEP 1: Place Lighter limit order with spread check
        print(f"\n▶ STEP 1: Lighter Limit Order ({lighter_order_side} {lighter_position_size} | Max Spread: {lighter_spread_max}% | {'WebSocket' if use_websocket else 'Polling'})")

        if use_websocket:
            lighter_result = await self.bot.lighter.place_limit_order_with_spread_check_ws(
                side=lighter_order_side,
                size=lighter_position_size,
                max_spread_pct=lighter_spread_max,
                timeout=lighter_timeout
            )
        else:
            lighter_result = await self.bot.lighter.place_limit_order_with_spread_check(
                side=lighter_order_side,
                size=lighter_position_size,
                max_spread_pct=lighter_spread_max,
                check_interval=2.0,
                timeout=lighter_timeout
            )

        if not lighter_result:
            print(f"\n❌ Lighter指値注文失敗")
            return {
                'success': False,
                'error': 'Lighter limit order failed or timeout'
            }

        lighter_order_id = lighter_result.get('order_id')
        print(f"\n✅ Order placed | ID: {lighter_order_id}")

        # STEP 2: Wait for Lighter order fill
        print(f"\n▶ STEP 2: Waiting for Fill...")

        # Get initial position size for WebSocket tracking
        initial_pos = await self.bot.lighter.get_position()
        initial_size = abs(initial_pos.get('size', 0)) if initial_pos else 0
        fill_timeout = lighter_timeout if lighter_timeout > 0 else 60.0

        if use_websocket:
            filled = await self.bot.lighter.wait_for_order_fill_ws(
                order_id=lighter_order_id,
                initial_size=initial_size,
                timeout=fill_timeout
            )
        else:
            filled = await self.bot.lighter.wait_for_order_fill(
                order_id=lighter_order_id,
                check_interval=2.0,
                timeout=fill_timeout
            )

        if not filled:
            print(f"\n❌ Lighter約定タイムアウト")
            # Try to cancel the order
            print(f"   注文をキャンセル中...")
            await self.bot.lighter.cancel_order(str(lighter_order_id))
            return {
                'success': False,
                'error': 'Lighter order fill timeout'
            }

        print(f"\n✅ Filled!")

        # STEP 3: Immediately place Paradex market order
        print(f"\n▶ STEP 3: Paradex Market Order ({paradex_order_side} {paradex_position_size} @ Market)")

        try:
            paradex_result = await self.bot.paradex.place_market_order(
                paradex_order_side,
                paradex_position_size
            )
        except Exception as e:
            print(f"\n❌ Paradex注文で例外発生: {e}")
            import traceback
            traceback.print_exc()
            paradex_result = None

        # Check if both orders succeeded
        if not paradex_result or isinstance(paradex_result, Exception):
            print(f"\n❌ Paradex注文失敗")
            print(f"   Result: {paradex_result}")
            print(f"   Type: {type(paradex_result)}")
            print(f"\n⚠️  警告: Lighterポジションは開いたままです！")
            print(f"   Lighter size: {lighter_position_size}")
            print(f"   Lighter side: {lighter_order_side}")
            return {
                'success': False,
                'error': f'Paradex market order failed: {paradex_result}'
            }

        print(f"\n✅ Paradex注文成功！")

        if not lighter_result or isinstance(lighter_result, Exception):
            print(f"\n❌ Lighter注文失敗: {lighter_result}")
            print(f"⚠️  Paradexポジションをクローズ中...")

            # Close Paradex position (reverse the opening side)
            paradex_close_side = 'SELL' if paradex_order_side == 'BUY' else 'BUY'
            close_result = await self.bot.paradex.place_market_order(paradex_close_side, paradex_position_size)

            if close_result:
                print(f"✅ Paradexポジションクローズ完了")
            else:
                print(f"❌ Paradexポジションクローズ失敗 - MANUAL INTERVENTION REQUIRED!")
                await self.notifier.send_error(
                    "CRITICAL: Failed to close Paradex position after Lighter failure",
                    f"Paradex size: {paradex_position_size}, Lighter error: {lighter_result}"
                )

            return {
                'success': False,
                'error': f'Lighter market order failed: {lighter_result}',
                'paradex_closed': close_result
            }

        # Verify filled sizes
        paradex_filled_size = await self._verify_filled_size(paradex_result, paradex_position_size, "Paradex")
        lighter_filled_size = await self._verify_filled_size(lighter_result, lighter_position_size, "Lighter")

        print(f"\n✅ 両取引所で約定完了!")
        print(f"   Paradex: {paradex_filled_size:.2f}/{paradex_position_size:.2f} @ ${paradex_price:.4f} (${paradex_filled_size * paradex_price:.2f})")
        print(f"   Lighter: {lighter_filled_size:.2f}/{lighter_position_size:.2f} @ ${lighter_price:.4f} (${lighter_filled_size * lighter_price:.2f})")

        # Step 2: Check for size mismatch and apply hybrid adjustment if needed
        print(f"\n📊 Position Size Check: Paradex {paradex_filled_size:.2f}/{paradex_position_size:.2f} | Lighter {lighter_filled_size:.2f}/{lighter_position_size:.2f}")

        paradex_total_filled = paradex_filled_size
        lighter_total_filled = lighter_filled_size

        # Check if adjustment is needed (tolerance: 0.5 units or 1%)
        paradex_shortage_tolerance = max(0.5, paradex_position_size * 0.01)
        lighter_shortage_tolerance = max(0.5, lighter_position_size * 0.01)
        paradex_shortage = paradex_position_size - paradex_total_filled
        lighter_shortage = lighter_position_size - lighter_total_filled

        if abs(paradex_shortage) > paradex_shortage_tolerance or abs(lighter_shortage) > lighter_shortage_tolerance:
            print(f"\n⚠️  ポジション調整が必要")
            print(f"   Paradex不足: {paradex_shortage:.2f} (許容誤差: {paradex_shortage_tolerance:.2f})")
            print(f"   Lighter不足: {lighter_shortage:.2f} (許容誤差: {lighter_shortage_tolerance:.2f})")

            # Apply hybrid retry logic for adjustment
            MAX_RETRIES = 3

            for attempt in range(1, MAX_RETRIES + 1):
                print(f"\n{'='*60}")
                print(f"📍調整 Attempt {attempt}/{MAX_RETRIES}")
                print(f"{'='*60}")

                # Calculate remaining shortage
                paradex_shortage = paradex_position_size - paradex_total_filled
                lighter_shortage = lighter_position_size - lighter_total_filled

                # If both are filled, we're done
                if abs(paradex_shortage) <= paradex_shortage_tolerance and abs(lighter_shortage) <= lighter_shortage_tolerance:
                    print(f"✅ Position fully filled!")
                    print(f"   Paradex: {paradex_total_filled:.2f}/{paradex_position_size:.2f}")
                    print(f"   Lighter: {lighter_total_filled:.2f}/{lighter_position_size:.2f}")
                    break

                # Execute shortage fill orders
                print(f"   🔄 Filling shortage:")
                print(f"      Paradex: {paradex_shortage:.2f} units")
                print(f"      Lighter: {lighter_shortage:.2f} units")

                tasks = []
                if abs(paradex_shortage) > 0.1:
                    tasks.append(('paradex', self.bot.paradex.place_market_order('BUY', abs(paradex_shortage))))
                if abs(lighter_shortage) > 0.1:
                    tasks.append(('lighter', self.bot.lighter.place_market_order('SELL', abs(lighter_shortage))))

                if tasks:
                    results = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)

                    for i, (exchange, _) in enumerate(tasks):
                        result = results[i]
                        success = not isinstance(result, Exception) and result

                        if exchange == 'paradex' and success:
                            filled = await self._verify_filled_size(result, abs(paradex_shortage), "Paradex")
                            paradex_total_filled += filled
                        elif exchange == 'lighter' and success:
                            filled = await self._verify_filled_size(result, abs(lighter_shortage), "Lighter")
                            lighter_total_filled += filled

                print(f"\n📊 Adjusted Fill Status:")
                print(f"   Paradex: {paradex_total_filled:.2f}/{paradex_position_size:.2f} ({paradex_total_filled/paradex_position_size*100:.1f}%)")
                print(f"   Lighter: {lighter_total_filled:.2f}/{lighter_position_size:.2f} ({lighter_total_filled/lighter_position_size*100:.1f}%)")

                # Check if we're close enough
                fill_tolerance = 0.99  # 99% fill is acceptable
                paradex_fill_ratio = paradex_total_filled / paradex_position_size
                lighter_fill_ratio = lighter_total_filled / lighter_position_size

                if paradex_fill_ratio >= fill_tolerance and lighter_fill_ratio >= fill_tolerance:
                    print(f"✅ Position sufficiently filled (>= {fill_tolerance*100:.0f}%)")
                    break

                # If this was the last attempt and we still have shortage, trigger emergency close
                if attempt == MAX_RETRIES:
                    print(f"\n⚠️  MAX RETRIES REACHED - Position not fully filled")
                    print(f"   Paradex filled: {paradex_total_filled:.2f}/{paradex_position_size:.2f}")
                    print(f"   Lighter filled: {lighter_total_filled:.2f}/{lighter_position_size:.2f}")

                    # Emergency: Close all positions and retry from scratch
                    if paradex_total_filled > 0 or lighter_total_filled > 0:
                        print(f"\n🚨 Triggering emergency closure...")

                        # Close whatever we managed to fill with independent sizes
                        emergency_success = await self._emergency_close_all(
                            paradex_size=paradex_total_filled,
                            lighter_size=lighter_total_filled
                        )

                        if emergency_success:
                            print(f"\n🔄 Restarting position opening from scratch...")
                            await asyncio.sleep(5)  # Wait 5 seconds before retry
                            # Recursive retry: call this method again
                            return await self.open_delta_neutral_position()
                        else:
                            print(f"\n❌ Emergency close failed - MANUAL INTERVENTION REQUIRED")
                            return {
                                'success': False,
                                'error': 'Emergency close failed after max retries'
                            }

                    # No positions to close, just fail
                    return {
                        'success': False,
                        'error': 'Max retries reached without sufficient fill'
                    }

                # Wait a bit before retry
                if attempt < MAX_RETRIES:
                    print(f"\n⏳ Waiting 3 seconds before retry...")
                    await asyncio.sleep(3)
        else:
            print(f"\n✅ ポジションサイズOK - 調整不要")

        # At this point, we have a successful fill (or broke out of loop)
        paradex_success = paradex_total_filled >= paradex_position_size * 0.99
        lighter_success = lighter_total_filled >= lighter_position_size * 0.99

        # Check if both succeeded
        if paradex_success and lighter_success:
            # Use actual filled sizes
            actual_position_size = min(paradex_total_filled, lighter_total_filled)
            self.position_open = True
            self.current_position = {
                'timestamp': datetime.now().isoformat(),
                'size': actual_position_size,  # Use actual filled size (for close-all)
                'paradex_target_size': paradex_position_size,  # Original Paradex target
                'lighter_target_size': lighter_position_size,   # Original Lighter target
                'paradex_filled': paradex_total_filled,
                'lighter_filled': lighter_total_filled,
                'paradex_price': paradex_price,
                'lighter_price': lighter_price,
                'paradex_side': paradex_side,  # 'LONG' or 'SHORT'
                'lighter_side': lighter_side,   # 'LONG' or 'SHORT'
                'paradex_fill_ratio': (paradex_total_filled/paradex_position_size) * 100,
                'lighter_fill_ratio': (lighter_total_filled/lighter_position_size) * 100,
            }

            # Save position to file for emergency close
            self._save_position_to_file()

            print(f"\n✅ Position Opened: Paradex {paradex_total_filled:.2f}/{paradex_position_size:.2f} ({paradex_total_filled/paradex_position_size*100:.0f}%) | Lighter {lighter_total_filled:.2f}/{lighter_position_size:.2f} ({lighter_total_filled/lighter_position_size*100:.0f}%)")

            # Send Discord notification with balance info
            notification_data = {
                **self.current_position,
                'paradex_balance': paradex_balance,
                'lighter_balance': lighter_balance
            }
            await self.notifier.send_position_opened(notification_data)

            return {
                'success': True,
                'position': self.current_position,
                'paradex_filled': paradex_total_filled,
                'lighter_filled': lighter_total_filled
            }

        # If we got here without returning, something went wrong
        print("\n❌ Failed to open delta neutral position")
        print(f"   Paradex fill: {paradex_total_filled:.2f}/{paradex_position_size:.2f}")
        print(f"   Lighter fill: {lighter_total_filled:.2f}/{lighter_position_size:.2f}")

        return {
            'success': False,
            'error': 'Insufficient fill after retries',
            'paradex_filled': paradex_total_filled,
            'lighter_filled': lighter_total_filled
        }

    async def close_delta_neutral_position(self) -> Dict[str, Any]:
        """
        Close delta neutral position:
        - Paradex: Close LONG (SELL)
        - Lighter: Close SHORT (BUY)

        Returns:
            Results of position closing
        """
        if not self.position_open or not self.current_position:
            print("⚠️  No open position to close")
            return {'success': False, 'error': 'No open position'}

        print("\n" + "="*60)
        print("🔄 Closing Delta Neutral Position")
        print("="*60)

        # Get independent position sizes and sides for each exchange
        paradex_position_size = self.current_position.get('paradex_filled', self.current_position['size'])
        lighter_position_size = self.current_position.get('lighter_filled', self.current_position['size'])
        paradex_side = self.current_position.get('paradex_side', 'LONG')  # Default to LONG for backward compatibility
        lighter_side = self.current_position.get('lighter_side', 'SHORT')  # Default to SHORT for backward compatibility

        print(f"\n📊 Position to close:")
        print(f"   Paradex ({paradex_side}): {paradex_position_size:.2f} units")
        print(f"   Lighter ({lighter_side}): {lighter_position_size:.2f} units")

        # Get and display current balances before closing
        balances = await self.get_available_balance()
        paradex_balance = balances.get('paradex', 0)
        lighter_balance = balances.get('lighter', 0)

        # Get spread monitoring configuration
        max_spread_pct = self.bot.config.spread_max_pct
        check_interval = self.bot.config.spread_check_interval
        timeout = self.bot.config.spread_check_timeout

        # Wait for tight spread before closing
        price_result = await self._wait_for_tight_spread(max_spread_pct, check_interval, timeout)

        if price_result is None:
            print("⚠️  Failed to achieve target spread within timeout for closing")
            print("   Using saved entry prices as reference...")
            # Use entry prices if spread timeout
            paradex_price = self.current_position.get('paradex_price', 0)
            lighter_price = self.current_position.get('lighter_price', 0)
        else:
            paradex_price, lighter_price = price_result

            # Final check if prices are available
            if not paradex_price or not lighter_price:
                print("⚠️  Failed to fetch current prices for closing")
                print("   Using saved entry prices as reference...")
                # Use entry prices if current prices unavailable
                paradex_price = self.current_position.get('paradex_price', 0)
                lighter_price = self.current_position.get('lighter_price', 0)

        # Determine close sides (reverse of opening sides)
        paradex_close_side = 'SELL' if paradex_side == 'LONG' else 'BUY'
        lighter_close_side = 'SELL' if lighter_side == 'LONG' else 'BUY'

        print(f"\n📊 Closing: Lighter {lighter_close_side} {lighter_position_size:.2f} → Paradex {paradex_close_side} {paradex_position_size:.2f}")
        if paradex_price and lighter_price:
            print(f"   Prices: Paradex ${paradex_price:.4f} | Lighter ${lighter_price:.4f}")

        # Get Lighter order configuration
        lighter_spread_max = self.bot.config.lighter_spread_max_pct
        lighter_timeout = self.bot.config.lighter_order_timeout

        # STEP 1: Place Lighter limit order with spread check
        use_websocket = self.bot.config.lighter_use_websocket
        print(f"\n▶ STEP 1: Lighter Close ({lighter_close_side} {lighter_position_size} | Max Spread: {lighter_spread_max}% | {'WebSocket' if use_websocket else 'Polling'})")

        if use_websocket:
            lighter_result = await self.bot.lighter.place_limit_order_with_spread_check_ws(
                side=lighter_close_side,
                size=lighter_position_size,
                max_spread_pct=lighter_spread_max,
                timeout=lighter_timeout
            )
        else:
            lighter_result = await self.bot.lighter.place_limit_order_with_spread_check(
                side=lighter_close_side,
                size=lighter_position_size,
                max_spread_pct=lighter_spread_max,
                check_interval=2.0,
                timeout=lighter_timeout
            )

        if not lighter_result:
            print(f"\n❌ Lighterクローズ指値注文失敗")
            print(f"⚠️  ポジションクローズ失敗 - MANUAL INTERVENTION REQUIRED!")
            await self.notifier.send_error(
                "CRITICAL: Failed to close Lighter position",
                f"Lighter size: {lighter_position_size}, Side: {lighter_close_side}"
            )
            return {
                'success': False,
                'error': 'Lighter close limit order failed or timeout'
            }

        lighter_order_id = lighter_result.get('order_id')
        print(f"\n✅ Lighter注文送信成功！ Order ID: {lighter_order_id}")

        # STEP 2: Wait for Lighter order fill
        print(f"\n▶ STEP 2: Waiting for Fill...")

        # Get initial position size for WebSocket tracking
        initial_pos = await self.bot.lighter.get_position()
        initial_size = abs(initial_pos.get('size', 0)) if initial_pos else paradex_position_size  # Fallback to paradex size

        fill_timeout = lighter_timeout if lighter_timeout > 0 else 60.0

        if use_websocket:
            filled = await self.bot.lighter.wait_for_order_fill_ws(
                order_id=lighter_order_id,
                initial_size=initial_size,
                timeout=fill_timeout
            )
        else:
            filled = await self.bot.lighter.wait_for_order_fill(
                order_id=lighter_order_id,
                check_interval=2.0,
                timeout=fill_timeout
            )

        if not filled:
            print(f"\n❌ Lighterクローズ約定タイムアウト")
            print(f"   注文をキャンセル中...")
            await self.bot.lighter.cancel_order(str(lighter_order_id))
            print(f"⚠️  ポジションクローズ失敗 - MANUAL INTERVENTION REQUIRED!")
            await self.notifier.send_error(
                "CRITICAL: Lighter close order fill timeout",
                f"Lighter size: {lighter_position_size}, Side: {lighter_close_side}"
            )
            return {
                'success': False,
                'error': 'Lighter close order fill timeout'
            }

        print(f"\n✅ Lighterクローズ約定確認！")

        # STEP 3: Immediately place Paradex market order
        print(f"\n▶ STEP 3: Paradex Market Close ({paradex_close_side} {paradex_position_size})")

        paradex_result = await self.bot.paradex.place_market_order(
            paradex_close_side,
            paradex_position_size
        )

        success = (
            not isinstance(paradex_result, Exception) and
            not isinstance(lighter_result, Exception)
        )

        # Calculate P&L with independent position sizes
        if success:
            entry_paradex_price = self.current_position['paradex_price']
            entry_lighter_price = self.current_position['lighter_price']

            # Calculate P&L for each exchange independently
            paradex_pnl = (paradex_price - entry_paradex_price) * paradex_position_size
            lighter_pnl = (entry_lighter_price - lighter_price) * lighter_position_size
            total_pnl = paradex_pnl + lighter_pnl

            print(f"\n💵 P&L: Paradex ${paradex_pnl:.2f} | Lighter ${lighter_pnl:.2f} | Total ${total_pnl:.2f}")

            # Save to history with independent sizes
            trade_data = {
                'entry_time': self.current_position['timestamp'],
                'exit_time': datetime.now().isoformat(),
                'paradex_size': paradex_position_size,
                'lighter_size': lighter_position_size,
                'paradex_entry_price': entry_paradex_price,
                'paradex_exit_price': paradex_price if paradex_price else 0,
                'lighter_entry_price': entry_lighter_price,
                'lighter_exit_price': lighter_price if lighter_price else 0,
                'paradex_pnl': paradex_pnl,
                'lighter_pnl': lighter_pnl,
                'total_pnl': total_pnl,
                'fees': 0  # TODO: Add fee tracking
            }
            self._save_to_history(trade_data)

            # Send Discord notification with balance info
            notification_data = {
                **trade_data,
                'paradex_balance': paradex_balance,
                'lighter_balance': lighter_balance
            }
            await self.notifier.send_position_closed(notification_data)

            self.position_open = False
            self.current_position = None

            # Remove position file
            self._remove_position_file()

            print("\n✅ Delta neutral position closed successfully!")
        else:
            print("\n❌ Failed to close delta neutral position")
            if isinstance(paradex_result, Exception):
                print(f"   Paradex error: {paradex_result}")
            if isinstance(lighter_result, Exception):
                print(f"   Lighter error: {lighter_result}")

        return {
            'success': success,
            'paradex': paradex_result,
            'lighter': lighter_result
        }

    async def run_loop(self, hold_time_hours: tuple = (2, 3), max_cycles: int = None):
        """
        Run automated delta neutral trading loop

        Args:
            hold_time_hours: Tuple of (min_hours, max_hours) for random hold time
            max_cycles: Maximum number of cycles (None = infinite)
        """
        print("\n" + "="*60)
        print("🔁 Starting Automated Trading Loop")
        print("="*60)
        if max_cycles:
            print(f"   Max cycles: {max_cycles}")
        else:
            print(f"   Max cycles: ∞ (infinite)")
        print("="*60)

        # Send loop started notification
        await self.notifier.send_loop_started(self.leverage, self.capital_percentage, max_cycles)

        cycle = 0

        try:
            while True:
                cycle += 1
                print(f"\n{'='*60}")
                print(f"📍 Cycle {cycle}")
                print(f"{'='*60}")

                # Open position
                open_result = await self.open_delta_neutral_position()

                if not open_result['success']:
                    print("⚠️  Failed to open position, retrying in 5 minutes...")
                    await asyncio.sleep(300)
                    continue

                # Random hold time between 2-3 hours
                hold_seconds = random.uniform(
                    hold_time_hours[0] * 3600,
                    hold_time_hours[1] * 3600
                )
                hold_minutes = hold_seconds / 60

                close_time = datetime.now() + timedelta(seconds=hold_seconds)
                print(f"\n⏰ Position will close at: {close_time.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"   (holding for {hold_minutes:.1f} minutes)")

                # Wait
                await asyncio.sleep(hold_seconds)

                # Close position
                close_result = await self.close_delta_neutral_position()

                if not close_result['success']:
                    print("❌ Failed to close position!")
                    print("⚠️  Manual intervention may be required")
                    # Still continue to next cycle
                    await asyncio.sleep(60)

                # Check if we should stop
                if max_cycles and cycle >= max_cycles:
                    print(f"\n✅ Completed {max_cycles} cycles. Stopping.")
                    await self.notifier.send_loop_stopped(f"Completed {max_cycles} cycles")
                    break

                # Small pause before next cycle
                print("\n⏸️  Waiting 30 seconds before next cycle...")
                await asyncio.sleep(30)

        except (KeyboardInterrupt, asyncio.CancelledError):
            print("\n\n⚠️  Loop interrupted by user")
            await self.notifier.send_loop_stopped("Interrupted by user")
            if self.position_open:
                print("🔄 Closing open position...")
                await self.close_delta_neutral_position()
            raise  # Re-raise to propagate to outer handler
        except Exception as e:
            print(f"\n❌ Error in loop: {e}")
            await self.notifier.send_error(f"Loop error: {e}", "Bot stopped due to error")
            if self.position_open:
                print("🔄 Attempting to close position...")
                await self.close_delta_neutral_position()
            raise
