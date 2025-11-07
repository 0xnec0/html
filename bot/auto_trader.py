"""
Automated trading loop with random position hold time
"""

import asyncio
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from .trading_bot import TradingBot


class AutoTrader:
    """Automated trading with random position holding"""

    def __init__(self, bot: TradingBot):
        """
        Initialize auto trader

        Args:
            bot: TradingBot instance
        """
        self.bot = bot
        self.running = False
        self.current_position = None

    def _random_hold_time(self, min_hours: float = 2.0, max_hours: float = 3.0) -> float:
        """
        Generate random hold time in seconds

        Args:
            min_hours: Minimum hours to hold
            max_hours: Maximum hours to hold

        Returns:
            Random time in seconds
        """
        hours = random.uniform(min_hours, max_hours)
        return hours * 3600  # Convert to seconds

    async def _wait_with_progress(self, seconds: float):
        """
        Wait with progress updates

        Args:
            seconds: Time to wait in seconds
        """
        end_time = datetime.now() + timedelta(seconds=seconds)

        print(f"\n⏰ Waiting until {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Duration: {seconds/3600:.2f} hours ({seconds:.0f} seconds)")

        # Update every 5 minutes
        update_interval = 300  # 5 minutes
        elapsed = 0

        while elapsed < seconds:
            await asyncio.sleep(min(update_interval, seconds - elapsed))
            elapsed += update_interval

            if elapsed < seconds:
                remaining = seconds - elapsed
                remaining_hours = remaining / 3600
                progress = (elapsed / seconds) * 100
                print(f"   ⏳ Progress: {progress:.1f}% | Remaining: {remaining_hours:.2f} hours")

    async def run_loop(
        self,
        side: str,
        amount: float,
        min_hold_hours: float = 2.0,
        max_hold_hours: float = 3.0,
        max_iterations: Optional[int] = None,
        paradex_only: bool = False,
        lighter_only: bool = False
    ):
        """
        Run automated trading loop

        Args:
            side: Initial order side ('BUY' or 'SELL')
            amount: Amount to trade
            min_hold_hours: Minimum hours to hold position
            max_hold_hours: Maximum hours to hold position
            max_iterations: Maximum number of iterations (None for infinite)
            paradex_only: Only trade on Paradex
            lighter_only: Only trade on Lighter
        """
        self.running = True
        iteration = 0
        current_side = side.upper()

        print("="*70)
        print("🤖 AUTO TRADING LOOP STARTED")
        print("="*70)
        print(f"Initial Side: {current_side}")
        print(f"Amount: {amount}")
        print(f"Hold Time: {min_hold_hours}-{max_hold_hours} hours")
        print(f"Max Iterations: {max_iterations if max_iterations else 'Unlimited'}")
        print(f"Exchanges: ", end="")
        if paradex_only:
            print("Paradex only")
        elif lighter_only:
            print("Lighter only")
        else:
            print("Both (Paradex + Lighter)")
        print("="*70)
        print("\n⚠️  Press Ctrl+C to stop gracefully")
        print()

        try:
            while self.running:
                iteration += 1

                if max_iterations and iteration > max_iterations:
                    print(f"\n✅ Reached maximum iterations ({max_iterations})")
                    break

                print(f"\n{'='*70}")
                print(f"🔄 ITERATION {iteration}")
                print(f"{'='*70}")

                # 1. Open position
                print(f"\n📈 Step 1: Opening {current_side} position")
                open_result = await self.bot.execute_simultaneous_trade(
                    side=current_side,
                    amount=amount,
                    paradex_only=paradex_only,
                    lighter_only=lighter_only
                )

                if not open_result['success']:
                    print(f"\n❌ Failed to open position. Retrying in 60 seconds...")
                    await asyncio.sleep(60)
                    continue

                self.current_position = {
                    'side': current_side,
                    'amount': amount,
                    'timestamp': datetime.now(),
                    'result': open_result
                }

                print(f"✅ Position opened: {current_side} {amount}")

                # 2. Random hold time
                hold_seconds = self._random_hold_time(min_hold_hours, max_hold_hours)
                print(f"\n⏱️  Step 2: Holding position")

                await self._wait_with_progress(hold_seconds)

                # 3. Close position (reverse side)
                close_side = 'SELL' if current_side == 'BUY' else 'BUY'
                print(f"\n📉 Step 3: Closing position with {close_side}")

                close_result = await self.bot.execute_simultaneous_trade(
                    side=close_side,
                    amount=amount,
                    paradex_only=paradex_only,
                    lighter_only=lighter_only
                )

                if not close_result['success']:
                    print(f"\n⚠️  Warning: Failed to close position properly")
                    print(f"   Attempting to continue...")
                else:
                    print(f"✅ Position closed: {close_side} {amount}")

                self.current_position = None

                # 4. Prepare for next iteration
                # Alternate side for next iteration
                current_side = close_side

                print(f"\n{'='*70}")
                print(f"✅ ITERATION {iteration} COMPLETED")
                print(f"   Next side: {current_side}")
                print(f"{'='*70}")

                # Short pause before next iteration
                if self.running and (not max_iterations or iteration < max_iterations):
                    print("\n⏸️  Pausing for 30 seconds before next iteration...")
                    await asyncio.sleep(30)

        except KeyboardInterrupt:
            print("\n\n🛑 Keyboard interrupt received")
            await self._graceful_shutdown()
        except Exception as e:
            print(f"\n\n❌ Error in trading loop: {e}")
            import traceback
            traceback.print_exc()
            await self._graceful_shutdown()
        finally:
            self.running = False

        print("\n" + "="*70)
        print("🏁 AUTO TRADING LOOP STOPPED")
        print(f"   Total iterations: {iteration}")
        print("="*70)

    async def _graceful_shutdown(self):
        """Handle graceful shutdown"""
        print("\n🛑 Initiating graceful shutdown...")
        self.running = False

        if self.current_position:
            print(f"\n⚠️  Open position detected!")
            print(f"   Side: {self.current_position['side']}")
            print(f"   Amount: {self.current_position['amount']}")
            print(f"   Opened at: {self.current_position['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")

            # Ask user if they want to close position
            print("\n❓ Do you want to close this position before stopping? (y/N): ", end="", flush=True)

            # For automated systems, default to not closing
            # In interactive mode, you could wait for user input
            # For now, we'll just warn
            print("\n⚠️  Position left open. Please close manually if needed.")

    def stop(self):
        """Stop the trading loop"""
        print("\n🛑 Stop requested...")
        self.running = False
