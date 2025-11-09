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
        print(f"\n⏳ 各取引所のスプレッドを監視中... (≤ {max_spread_pct}%)")
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

        # Debug: show raw responses
        print(f"   DEBUG - Paradex response: {paradex_balance_info}")
        print(f"   DEBUG - Lighter response: {lighter_balance_info}")

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
        print("   Strategy: Paradex LONG + Lighter SHORT")
        print(f"   Leverage: {self.leverage}x")
        print(f"   Capital: {self.capital_percentage*100}%")

        # Get and display current balances
        print("\n💰 Checking current balances...")
        balances = await self.get_available_balance()
        paradex_balance = balances.get('paradex', 0)
        lighter_balance = balances.get('lighter', 0)

        print(f"   Paradex: ${paradex_balance:.2f}")
        print(f"   Lighter:  ${lighter_balance:.2f}")
        print(f"   Total:    ${paradex_balance + lighter_balance:.2f}")

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

        # Calculate position size
        if self.usd_amount:
            # Calculate position size for each exchange to match USD amount as closely as possible
            paradex_size = int(self.usd_amount / paradex_price)
            lighter_size = int(self.usd_amount / lighter_price)

            # Use the smaller size to ensure both can be filled with similar USD amounts
            position_size = min(paradex_size, lighter_size)

            # Calculate actual USD amounts
            paradex_usd = position_size * paradex_price
            lighter_usd = position_size * lighter_price

            print(f"\n💵 Using fixed USD amount: ${self.usd_amount:.2f}")
            print(f"   Paradex price: ${paradex_price:.4f} → {position_size} units = ${paradex_usd:.2f}")
            print(f"   Lighter price: ${lighter_price:.4f} → {position_size} units = ${lighter_usd:.2f}")
            print(f"   Position size: {position_size} units")
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
            else:
                position_size = await self.calculate_position_size(avg_price, available_balance)
                # Round down to integer
                position_size = int(position_size)

        print(f"\n📊 Executing delta neutral strategy...")
        print(f"   Paradex: BUY {position_size} @ ${paradex_price:.4f}")
        print(f"   Lighter: SELL {position_size} @ ${lighter_price:.4f}")

        # Execute both orders simultaneously
        tasks = [
            self.bot.paradex.place_market_order('BUY', position_size),
            self.bot.lighter.place_market_order('SELL', position_size)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        paradex_result = results[0]
        lighter_result = results[1]

        paradex_success = not isinstance(paradex_result, Exception) and paradex_result
        lighter_success = not isinstance(lighter_result, Exception) and lighter_result

        # Check if both succeeded
        if paradex_success and lighter_success:
            self.position_open = True
            self.current_position = {
                'timestamp': datetime.now().isoformat(),
                'size': position_size,
                'paradex_price': paradex_price,
                'lighter_price': lighter_price,
                # Don't save SDK response objects (not JSON serializable)
                # Just save essential info for position tracking
            }

            # Save position to file for emergency close
            self._save_position_to_file()

            print("\n✅ Delta neutral position opened successfully!")

            # Send Discord notification with balance info
            notification_data = {
                **self.current_position,
                'paradex_balance': paradex_balance,
                'lighter_balance': lighter_balance
            }
            await self.notifier.send_position_opened(notification_data)

        # Handle partial failure - close the successful position
        elif paradex_success and not lighter_success:
            print("\n⚠️  Partial failure detected: Paradex succeeded but Lighter failed")
            print("🔄 Automatically closing Paradex position to maintain safety...")

            # Send partial failure notification
            await self.notifier.send_partial_failure("Paradex", position_size)

            try:
                # Close Paradex position (SELL to close LONG)
                close_result = await self.bot.paradex.place_market_order('SELL', position_size)
                if close_result:
                    print("✅ Paradex position closed successfully")
                else:
                    print("❌ Failed to close Paradex position - MANUAL INTERVENTION REQUIRED!")
                    await self.notifier.send_error(
                        "Failed to close Paradex position after partial failure",
                        f"Lighter error: {lighter_result}"
                    )
            except Exception as e:
                print(f"❌ Error closing Paradex position: {e}")
                print("⚠️  MANUAL INTERVENTION REQUIRED - Check Paradex for open position!")
                await self.notifier.send_error(
                    f"Error closing Paradex position: {e}",
                    "MANUAL INTERVENTION REQUIRED"
                )

            print(f"\n❌ Failed to open delta neutral position")
            print(f"   Lighter error: {lighter_result}")

        elif lighter_success and not paradex_success:
            print("\n⚠️  Partial failure detected: Lighter succeeded but Paradex failed")
            print("🔄 Automatically closing Lighter position to maintain safety...")

            # Send partial failure notification
            await self.notifier.send_partial_failure("Lighter", position_size)

            try:
                # Close Lighter position (BUY to close SHORT)
                close_result = await self.bot.lighter.place_market_order('BUY', position_size)
                if close_result:
                    print("✅ Lighter position closed successfully")
                else:
                    print("❌ Failed to close Lighter position - MANUAL INTERVENTION REQUIRED!")
                    await self.notifier.send_error(
                        "Failed to close Lighter position after partial failure",
                        f"Paradex error: {paradex_result}"
                    )
            except Exception as e:
                print(f"❌ Error closing Lighter position: {e}")
                print("⚠️  MANUAL INTERVENTION REQUIRED - Check Lighter for open position!")
                await self.notifier.send_error(
                    f"Error closing Lighter position: {e}",
                    "MANUAL INTERVENTION REQUIRED"
                )

            print(f"\n❌ Failed to open delta neutral position")
            print(f"   Paradex error: {paradex_result}")

        else:
            # Both failed
            print("\n❌ Failed to open delta neutral position")
            if isinstance(paradex_result, Exception):
                print(f"   Paradex error: {paradex_result}")
            if isinstance(lighter_result, Exception):
                print(f"   Lighter error: {lighter_result}")

        return {
            'success': paradex_success and lighter_success,
            'position': self.current_position if paradex_success and lighter_success else None,
            'paradex': paradex_result,
            'lighter': lighter_result
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

        position_size = self.current_position['size']

        # Get and display current balances before closing
        print("\n💰 Checking current balances...")
        balances = await self.get_available_balance()
        paradex_balance = balances.get('paradex', 0)
        lighter_balance = balances.get('lighter', 0)

        print(f"   Paradex: ${paradex_balance:.2f}")
        print(f"   Lighter:  ${lighter_balance:.2f}")
        print(f"   Total:    ${paradex_balance + lighter_balance:.2f}")

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

        print(f"\n📊 Closing positions...")
        if paradex_price:
            print(f"   Paradex: SELL {position_size} @ ${paradex_price:.4f}")
        else:
            print(f"   Paradex: SELL {position_size} @ (price unavailable)")

        if lighter_price:
            print(f"   Lighter: BUY {position_size} @ ${lighter_price:.4f}")
        else:
            print(f"   Lighter: BUY {position_size} @ (price unavailable)")

        # Execute both orders simultaneously
        tasks = [
            self.bot.paradex.place_market_order('SELL', position_size),
            self.bot.lighter.place_market_order('BUY', position_size)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        paradex_result = results[0]
        lighter_result = results[1]

        success = (
            not isinstance(paradex_result, Exception) and
            not isinstance(lighter_result, Exception)
        )

        # Calculate P&L
        if success:
            entry_paradex_price = self.current_position['paradex_price']
            entry_lighter_price = self.current_position['lighter_price']

            paradex_pnl = (paradex_price - entry_paradex_price) * position_size
            lighter_pnl = (entry_lighter_price - lighter_price) * position_size
            total_pnl = paradex_pnl + lighter_pnl

            print(f"\n💵 P&L Summary:")
            print(f"   Paradex (LONG): ${paradex_pnl:.2f}")
            print(f"   Lighter (SHORT): ${lighter_pnl:.2f}")
            print(f"   Total P&L: ${total_pnl:.2f}")

            # Save to history
            trade_data = {
                'entry_time': self.current_position['timestamp'],
                'exit_time': datetime.now().isoformat(),
                'size': position_size,
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
        print("🔁 Starting Delta Neutral Auto Loop")
        print("="*60)
        print(f"   Hold time: {hold_time_hours[0]}-{hold_time_hours[1]} hours")
        print(f"   Leverage: {self.leverage}x")
        print(f"   Capital: {self.capital_percentage*100}%")
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

        except KeyboardInterrupt:
            print("\n\n⚠️  Loop interrupted by user")
            await self.notifier.send_loop_stopped("Interrupted by user")
            if self.position_open:
                print("🔄 Closing open position...")
                await self.close_delta_neutral_position()
        except Exception as e:
            print(f"\n❌ Error in loop: {e}")
            await self.notifier.send_error(f"Loop error: {e}", "Bot stopped due to error")
            if self.position_open:
                print("🔄 Attempting to close position...")
                await self.close_delta_neutral_position()
            raise
