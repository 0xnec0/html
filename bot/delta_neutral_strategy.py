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
        self.notifier = DiscordNotifier()

        # Load existing position from file if it exists
        self.current_position = self.load_current_position()
        self.position_open = self.current_position is not None

        if self.position_open:
            print(f"ℹ️  既存のオープンポジションを検知しました:")
            print(f"   サイズ: {self.current_position.get('size', 'N/A')}")
            print(f"   タイムスタンプ: {self.current_position.get('timestamp', 'N/A')}")

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

    async def _check_funding_rate_opportunity(self) -> Optional[Dict[str, Any]]:
        """
        Check if there's a funding rate arbitrage opportunity

        Lighter: Hourly discrete funding with ±0.5% cap
        Paradex: Continuous funding (pro-rated) with ±5% annual cap

        Returns:
            Dict with funding rate analysis and recommendation:
            {
                'opportunity': bool,  # True if should open position
                'lighter_rate': float,
                'paradex_rate': float,
                'rate_diff_pct': float,
                'estimated_apy': float,
                'recommendation': str,  # 'LIGHTER_SHORT' or 'LIGHTER_LONG' or 'NO_POSITION'
                'reason': str
            }
            or None if error
        """
        if not self.bot.config.funding_rate_enabled:
            return {
                'opportunity': True,  # Bypass check if disabled
                'lighter_rate': 0,
                'paradex_rate': 0,
                'rate_diff_pct': 0,
                'estimated_apy': 0,
                'recommendation': 'NO_CHECK',
                'paradex_side': 'BUY',  # Default to standard strategy
                'lighter_side': 'SELL',
                'reason': 'Funding rate check disabled in config'
            }

        print(f"\n💹 ファンディングレートアービトラージ機会をチェック中...")

        try:
            # Get funding rates from both exchanges
            lighter_funding = await self.bot.lighter.get_funding_rate()
            paradex_funding = await self.bot.paradex.get_funding_rate()

            if not lighter_funding or not paradex_funding:
                print("⚠️  ファンディングレート取得失敗、スキップします")
                return {
                    'opportunity': True,  # Proceed anyway
                    'lighter_rate': 0,
                    'paradex_rate': 0,
                    'rate_diff_pct': 0,
                    'estimated_apy': 0,
                    'recommendation': 'DATA_UNAVAILABLE',
                    'paradex_side': 'BUY',  # Default to standard strategy
                    'lighter_side': 'SELL',
                    'reason': 'Could not fetch funding rates'
                }

            # Extract rates (convert to comparable format)
            # Lighter: hourly rate, Paradex: 8-hour rate
            lighter_rate_hourly = lighter_funding['funding_rate']
            paradex_rate_8h = paradex_funding['funding_rate']

            # Convert Paradex 8-hour rate to hourly for comparison
            paradex_rate_hourly = paradex_rate_8h / 8

            print(f"   Lighter: {lighter_rate_hourly*100:.4f}%/時 (離散型)")
            print(f"   Paradex: {paradex_rate_hourly*100:.4f}%/時 (連続型、{paradex_rate_8h*100:.4f}%/8時間)")

            # Calculate absolute difference
            rate_diff = abs(lighter_rate_hourly - paradex_rate_hourly)
            rate_diff_pct = rate_diff * 100  # Convert to percentage

            # Estimate annual yield (conservative: 16 hours/day holding, 250 trading days)
            # Lighter discrete: full hour payment, Paradex: pro-rated
            hours_per_year = 16 * 250  # Conservative estimate
            estimated_apy = rate_diff * hours_per_year * 100  # As percentage

            print(f"   差額: {rate_diff_pct:.4f}%/時")
            print(f"   推定APY: {estimated_apy:.2f}%")

            # Decision logic
            min_diff_pct = self.bot.config.funding_rate_min_diff_pct
            target_apy = self.bot.config.funding_rate_target_apy

            if rate_diff_pct < min_diff_pct:
                print(f"   ⚠️  差額が閾値未満 ({min_diff_pct}%)")
                return {
                    'opportunity': False,
                    'lighter_rate': lighter_rate_hourly,
                    'paradex_rate': paradex_rate_hourly,
                    'rate_diff_pct': rate_diff_pct,
                    'estimated_apy': estimated_apy,
                    'recommendation': 'NO_POSITION',
                    'reason': f'Rate difference {rate_diff_pct:.4f}% below threshold {min_diff_pct}%'
                }

            # Determine position direction based on funding rates
            # Rule: SHORT on the exchange with HIGHER funding rate (receive more)
            #       LONG on the exchange with LOWER funding rate (pay less)
            if lighter_rate_hourly > paradex_rate_hourly:
                # Lighter has higher rate → SHORT on Lighter, LONG on Paradex
                paradex_side = 'BUY'
                lighter_side = 'SELL'
                recommendation = 'LIGHTER_SHORT_PARADEX_LONG'
                reason = f'Lighter rate ({lighter_rate_hourly*100:.4f}%) > Paradex rate ({paradex_rate_hourly*100:.4f}%)'
            else:
                # Paradex has higher rate → SHORT on Paradex, LONG on Lighter
                paradex_side = 'SELL'
                lighter_side = 'BUY'
                recommendation = 'PARADEX_SHORT_LIGHTER_LONG'
                reason = f'Paradex rate ({paradex_rate_hourly*100:.4f}%) > Lighter rate ({lighter_rate_hourly*100:.4f}%)'

            print(f"   ✅ 機会あり: {recommendation}")
            print(f"   理由: {reason}")
            print(f"   Paradex: {paradex_side}, Lighter: {lighter_side}")

            return {
                'opportunity': True,
                'lighter_rate': lighter_rate_hourly,
                'paradex_rate': paradex_rate_hourly,
                'rate_diff_pct': rate_diff_pct,
                'estimated_apy': estimated_apy,
                'recommendation': recommendation,
                'paradex_side': paradex_side,  # 'BUY' or 'SELL'
                'lighter_side': lighter_side,  # 'BUY' or 'SELL'
                'reason': reason
            }

        except Exception as e:
            print(f"❌ ファンディングレートチェックエラー: {e}")
            import traceback
            traceback.print_exc()
            return {
                'opportunity': True,  # Proceed anyway on error
                'lighter_rate': 0,
                'paradex_rate': 0,
                'rate_diff_pct': 0,
                'estimated_apy': 0,
                'recommendation': 'ERROR',
                'paradex_side': 'BUY',  # Default to standard strategy
                'lighter_side': 'SELL',
                'reason': f'Error checking funding rates: {e}'
            }

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

    def _save_pending_order(self, order_id: str) -> None:
        """
        Save pending order ID to file for cleanup on next run

        Args:
            order_id: Order ID to save
        """
        try:
            pending_orders_file = ".pending_lighter_orders.json"
            pending_orders = []

            # Load existing orders
            if os.path.exists(pending_orders_file):
                try:
                    with open(pending_orders_file, 'r') as f:
                        pending_orders = json.load(f)
                except Exception:
                    pending_orders = []

            # Add new order if not already present
            if order_id not in pending_orders:
                pending_orders.append(order_id)

            # Save back to file
            with open(pending_orders_file, 'w') as f:
                json.dump(pending_orders, f)

        except Exception as e:
            # Not critical - just log
            pass

    def _clear_pending_orders_file(self) -> None:
        """Clear the pending orders file after successful fill"""
        try:
            pending_orders_file = ".pending_lighter_orders.json"
            with open(pending_orders_file, 'w') as f:
                json.dump([], f)
        except Exception:
            pass

    async def _cancel_existing_pending_orders(self) -> None:
        """
        Cancel all existing pending orders on Lighter before placing new orders

        This prevents order accumulation from previous runs or failed attempts.
        Reads order IDs from .pending_orders.json if it exists.
        """
        try:
            print(f"   未約定注文のクリーンアップを試行中...")

            # Try to load pending orders from file
            pending_orders_file = ".pending_lighter_orders.json"
            if os.path.exists(pending_orders_file):
                try:
                    with open(pending_orders_file, 'r') as f:
                        pending_orders = json.load(f)

                    if pending_orders and len(pending_orders) > 0:
                        print(f"   前回の未約定注文を発見: {len(pending_orders)}個")

                        cancelled = 0
                        for order_id in pending_orders:
                            try:
                                success = await self.bot.lighter.cancel_order(str(order_id))
                                if success:
                                    cancelled += 1
                            except Exception:
                                pass  # Order might already be filled/cancelled
                            await asyncio.sleep(0.1)  # Rate limiting

                        print(f"   ✓ {cancelled}個の注文をキャンセルしました")

                        # Clear the file
                        with open(pending_orders_file, 'w') as f:
                            json.dump([], f)
                    else:
                        print(f"   ✓ 前回の未約定注文はありません")
                except Exception as e:
                    print(f"   ⚠️  ファイル読み込みエラー: {e}")
            else:
                print(f"   ✓ 前回の未約定注文はありません")

        except Exception as e:
            print(f"   ⚠️  クリーンアップ中にエラー: {e}")
            # Continue anyway - not critical

    async def _cancel_all_pending_orders(self, all_order_ids: list, filled_order_id: str = None) -> None:
        """
        Cancel all pending orders except the filled one

        Args:
            all_order_ids: List of all order IDs that were placed
            filled_order_id: Order ID that was filled (optional, will not be cancelled)
        """
        if not all_order_ids:
            return

        print(f"\n🗑️  未約定注文をキャンセル中... ({len(all_order_ids)}個)")

        cancelled_count = 0
        failed_count = 0

        for order_id in all_order_ids:
            # Skip the filled order
            if filled_order_id and order_id == filled_order_id:
                continue

            try:
                success = await self.bot.lighter.cancel_order(str(order_id))
                if success:
                    cancelled_count += 1
                    print(f"   ✓ キャンセル成功: {order_id}")
                else:
                    failed_count += 1
                    print(f"   ⚠️  キャンセル失敗: {order_id}")
            except Exception as e:
                failed_count += 1
                print(f"   ❌ キャンセルエラー {order_id}: {e}")

            # Small delay to avoid rate limiting
            await asyncio.sleep(0.1)

        print(f"   完了: 成功 {cancelled_count}, 失敗 {failed_count}")

    async def _wait_for_lighter_fill_via_websocket(self, initial_position_size: float, target_size: float, timeout: int = 30) -> bool:
        """
        Wait for order to fill by monitoring position changes via WebSocket

        Note: Falls back to simple timeout if WebSocket is not available.

        Args:
            initial_position_size: Position size before order
            target_size: Expected position size after fill
            timeout: Maximum wait time in seconds

        Returns:
            True if filled, False if timeout
        """
        try:
            print(f"\n🔌 WebSocketで約定監視を試行中...")
            print(f"   初期ポジション: {initial_position_size:.2f}")
            print(f"   目標ポジション: {target_size:.2f}")
            print(f"   タイムアウト: {timeout}秒")

            filled_event = asyncio.Event()

            async def on_account_update(account_data: dict):
                """Callback for account updates"""
                try:
                    position = await self.bot.lighter.get_position_from_account(account_data)
                    if position:
                        current_size = position.get('size', 0)
                        print(f"\r   📊 現在のポジション: {current_size:.2f} (目標: {target_size:.2f})", end='', flush=True)

                        # Check if target reached
                        if abs(current_size - target_size) < 0.01:  # Allow small tolerance
                            print(f"\n   ✅ 約定確認！ポジション: {current_size:.2f}")
                            filled_event.set()
                except Exception as e:
                    print(f"\n   ❌ アカウント更新処理エラー: {e}")

            # Start WebSocket subscription in background
            websocket_task = asyncio.create_task(
                self.bot.lighter.subscribe_to_account_updates(on_account_update)
            )

            try:
                # Wait for fill or timeout
                await asyncio.wait_for(filled_event.wait(), timeout=timeout)
                print(f"\n   ✓ WebSocketで約定を検知しました！")
                return True

            except asyncio.TimeoutError:
                print(f"\n   ⏰ タイムアウト: {timeout}秒以内に約定を確認できませんでした")
                return False

            finally:
                # Cancel WebSocket task
                websocket_task.cancel()
                try:
                    await websocket_task
                except asyncio.CancelledError:
                    pass

        except AttributeError:
            # WebSocket method not available - fallback to polling
            print(f"\n   ⚠️  WebSocket機能が利用できません（SDK未サポート）")
            print(f"   ポーリング方式で{timeout}秒待機します...")
            await asyncio.sleep(timeout)
            # Assume filled after waiting (optimistic approach for limit orders)
            return True

        except Exception as e:
            print(f"\n   ❌ WebSocket監視エラー: {e}")
            print(f"   ポーリング方式で{timeout}秒待機します...")
            await asyncio.sleep(timeout)
            return True

    async def _place_lighter_limit_with_price_update(self, side: str, size: float, max_attempts: int = 12, wait_seconds: int = 5, use_websocket: bool = True) -> Optional[Dict[str, Any]]:
        """
        Place Lighter limit order with price updates until filled

        Args:
            side: Order side ('BUY' or 'SELL')
            size: Order size
            max_attempts: Maximum number of attempts (default: 12)
            wait_seconds: Seconds to wait between attempts (default: 5)
            use_websocket: Use WebSocket for fill detection (default: True)

        Returns:
            Order result if filled, None if failed
        """
        print(f"\n📍 Lighter指値注文（価格自動更新）")
        print(f"   注文方向: {side}")
        print(f"   目標サイズ: {size:.2f}")
        print(f"   最大試行回数: {max_attempts}")
        print(f"   更新間隔: {wait_seconds}秒")
        print(f"   WebSocket検知: {'有効' if use_websocket else '無効'}")

        # Get initial position size (for WebSocket detection and existing position check)
        initial_position_size = 0.0
        try:
            account_data = await self.bot.lighter.get_account_balance()
            if account_data:
                position = await self.bot.lighter.get_position_from_account(account_data)
                if position:
                    initial_position_size = position.get('size', 0)
                    print(f"   初期ポジション: {initial_position_size:.2f}")

                    # Check if we already have the target position
                    # For SELL orders, we expect position size to be -size (short position)
                    # For BUY orders, we expect position size to be +size (long position)
                    expected_position = -size if side == 'SELL' else size
                    if abs(initial_position_size - expected_position) < size * 0.1:  # Allow 10% tolerance
                        print(f"   ✅ すでに目標ポジションを保有しています")
                        print(f"   現在: {initial_position_size:.2f}, 期待値: {expected_position:.2f}")
                        return {
                            'order_id': 'existing',
                            'tx_hash': 'existing',
                            'filled_size': size,
                            'filled_price': 0,  # Unknown
                            'status': 'FILLED'
                        }
        except Exception as e:
            print(f"   ⚠️  初期ポジション取得失敗: {e}")
            if use_websocket:
                use_websocket = False

        current_order_id = None
        all_order_ids = []  # Track all placed orders for cleanup

        # IMPORTANT: Cancel any pending orders from previous runs before starting
        print(f"\n🧹 事前クリーンアップ: 既存の未約定注文を確認中...")
        await self._cancel_existing_pending_orders()

        for attempt in range(1, max_attempts + 1):
            print(f"\n{'='*60}")
            print(f"🔄 試行 {attempt}/{max_attempts}")
            print(f"{'='*60}")

            # STEP 1: Cancel previous order from this loop (if exists)
            if current_order_id:
                print(f"   🗑️  前回の注文をキャンセル中: {current_order_id}")
                await self.bot.lighter.cancel_order(str(current_order_id))
                await asyncio.sleep(0.5)  # Wait for cancellation to process

            # STEP 2: Get latest bid/ask
            bid_ask = await self.bot.lighter.get_bid_ask()
            if not bid_ask:
                print("❌ 価格取得失敗")
                await asyncio.sleep(wait_seconds)
                continue

            best_bid, best_ask = bid_ask

            # Use best ask for SELL (most likely to fill) or best bid for BUY
            if side == 'SELL':
                limit_price = best_ask
                price_label = "Best Ask"
            else:  # BUY
                limit_price = best_bid
                price_label = "Best Bid"

            print(f"   最新価格: Bid ${best_bid:.4f} | Ask ${best_ask:.4f}")
            print(f"   指値価格: ${limit_price:.4f} ({price_label})")

            # STEP 3: Place new limit order
            order_result = await self.bot.lighter.place_limit_order(side, size, limit_price)

            if not order_result:
                print("❌ 注文失敗")
                await asyncio.sleep(wait_seconds)
                continue

            current_order_id = order_result.get('order_id')
            tx_hash = order_result.get('tx_hash')
            all_order_ids.append(current_order_id)  # Track this order

            # Save order ID to file for cleanup on next run
            self._save_pending_order(current_order_id)

            print(f"   ✓ 注文送信完了")
            print(f"   Order ID: {current_order_id}")
            print(f"   TX Hash: {tx_hash}")

            # Check if filled using WebSocket or polling
            if use_websocket:
                # Use WebSocket to detect fill
                # For SELL orders, position size becomes negative (subtract)
                # For BUY orders, position size becomes positive (add)
                if side == 'SELL':
                    target_position_size = initial_position_size - size
                else:  # BUY
                    target_position_size = initial_position_size + size

                filled = await self._wait_for_lighter_fill_via_websocket(
                    initial_position_size,
                    target_position_size,
                    timeout=wait_seconds
                )

                if filled:
                    print(f"   ✅ 注文約定完了！")
                    # Cancel all other pending orders
                    await self._cancel_all_pending_orders(all_order_ids, current_order_id)
                    # Clear pending orders file
                    self._clear_pending_orders_file()
                    return {
                        **order_result,
                        'filled_size': size,
                        'filled_price': limit_price,
                        'status': 'FILLED'
                    }
            else:
                # Fallback: Wait and assume filled if tx succeeded
                print(f"   ⏳ {wait_seconds}秒待機中...")
                await asyncio.sleep(wait_seconds)

                if tx_hash:
                    print(f"   ✅ 注文約定完了！")
                    # Cancel all other pending orders
                    await self._cancel_all_pending_orders(all_order_ids, current_order_id)
                    # Clear pending orders file
                    self._clear_pending_orders_file()
                    return {
                        **order_result,
                        'filled_size': size,
                        'filled_price': limit_price,
                        'status': 'FILLED'
                    }

            print(f"   ⚠️  約定未確認 - 価格を更新して再試行...")

        # Max attempts reached
        print(f"\n❌ 最大試行回数到達 - Lighter注文失敗")
        # Cancel all pending orders
        await self._cancel_all_pending_orders(all_order_ids)

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

    async def _emergency_close_all(self, position_size: float) -> bool:
        """
        Emergency close all positions and reset

        Args:
            position_size: Size of positions to close

        Returns:
            True if successfully closed
        """
        print("\n🚨 EMERGENCY: Closing all positions...")
        print(f"   Closing {position_size:.2f} units on both exchanges")

        try:
            # Close both positions
            tasks = [
                self.bot.paradex.place_market_order('SELL', position_size),  # Close LONG
                self.bot.lighter.place_market_order('BUY', position_size)    # Close SHORT
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
                    f"Closed {position_size:.2f} units on both exchanges after retry failure"
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
        # Safety check: prevent opening multiple positions
        if self.position_open:
            print("⚠️  ポジションは既にオープンしています。先に決済してください。")
            print(f"   現在のポジションサイズ: {self.current_position.get('size', 'N/A')}")
            return {'success': False, 'error': 'Position already open'}

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

        # ===== スプレッド監視機能（コメントアウト） =====
        # Get spread monitoring configuration
        # max_spread_pct = self.bot.config.spread_max_pct
        # check_interval = self.bot.config.spread_check_interval
        # timeout = self.bot.config.spread_check_timeout

        # Wait for tight spread
        # price_result = await self._wait_for_tight_spread(max_spread_pct, check_interval, timeout)

        # if price_result is None:
        #     print("❌ Failed to achieve target spread within timeout")
        #     return {'success': False, 'error': 'Spread timeout'}

        # paradex_price, lighter_price = price_result
        # ===== スプレッド監視機能ここまで =====

        # 直接価格を取得（スプレッド監視なし）
        print(f"\n💰 現在価格を取得中...")
        paradex_bid_ask = await self.bot.paradex.get_bid_ask()
        lighter_bid_ask = await self.bot.lighter.get_bid_ask()

        if not paradex_bid_ask or not lighter_bid_ask:
            print("❌ Failed to get prices")
            return {'success': False, 'error': 'Price fetch failed'}

        paradex_bid, paradex_ask = paradex_bid_ask
        lighter_bid, lighter_ask = lighter_bid_ask

        paradex_price = (paradex_bid + paradex_ask) / 2
        lighter_price = (lighter_bid + lighter_ask) / 2

        print(f"   Paradex: ${paradex_price:.4f} (Bid: ${paradex_bid:.4f}, Ask: ${paradex_ask:.4f})")
        print(f"   Lighter: ${lighter_price:.4f} (Bid: ${lighter_bid:.4f}, Ask: ${lighter_ask:.4f})")

        if not paradex_price or not lighter_price:
            print("❌ Failed to get prices")
            return {'success': False, 'error': 'Price fetch failed'}

        avg_price = (paradex_price + lighter_price) / 2

        # Check funding rate arbitrage opportunity
        funding_check = await self._check_funding_rate_opportunity()

        if funding_check and not funding_check['opportunity']:
            print(f"⚠️  ファンディングレート機会なし: {funding_check['reason']}")
            return {'success': False, 'error': 'No funding rate opportunity', 'funding_check': funding_check}

        if funding_check and funding_check['opportunity']:
            print(f"✅ ファンディングレート機会あり!")
            print(f"   推定APY: {funding_check['estimated_apy']:.2f}%")
            print(f"   戦略: {funding_check['recommendation']}")

        # Get position sides from funding rate check
        paradex_side = funding_check.get('paradex_side', 'BUY')  # Default to BUY if not specified
        lighter_side = funding_check.get('lighter_side', 'SELL')  # Default to SELL if not specified

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

        print(f"\n📊 Executing delta neutral strategy (FUNDING RATE BASED)")
        print(f"   Target: {position_size} units")
        print(f"   Strategy: Lighter指値 → Paradex成り行き")
        print(f"   Paradex: {paradex_side} @ ${paradex_price:.4f}")
        print(f"   Lighter: {lighter_side} @ ${lighter_price:.4f}")

        # Step 1: Place Lighter limit order with price updates
        print(f"\n{'='*60}")
        print(f"STEP 1: Lighter指値注文（価格自動更新）- {lighter_side}")
        print(f"{'='*60}")

        lighter_result = await self._place_lighter_limit_with_price_update(
            side=lighter_side,
            size=position_size,
            max_attempts=12,
            wait_seconds=5,
            use_websocket=self.bot.config.lighter_use_websocket
        )

        if not lighter_result:
            print(f"\n❌ Lighter注文失敗 - ポジションオープン中止")
            return {
                'success': False,
                'error': 'Lighter limit order failed after max attempts'
            }

        lighter_filled_size = lighter_result.get('filled_size', position_size)
        lighter_filled_price = lighter_result.get('filled_price', lighter_price)

        print(f"\n✅ Lighter約定完了!")
        print(f"   約定サイズ: {lighter_filled_size:.2f}")
        print(f"   約定価格: ${lighter_filled_price:.4f}")

        # Step 2: Place Paradex market order
        print(f"\n{'='*60}")
        print(f"STEP 2: Paradex成り行き注文 - {paradex_side}")
        print(f"{'='*60}")
        print(f"   {paradex_side} {position_size} @ market")

        paradex_result = await self.bot.paradex.place_market_order(paradex_side, position_size)

        if not paradex_result or isinstance(paradex_result, Exception):
            print(f"\n⚠️  Paradex注文失敗 - Lighterポジションをクローズ中...")

            # Close Lighter position (opposite side of what was opened)
            close_side = 'BUY' if lighter_side == 'SELL' else 'SELL'
            close_result = await self.bot.lighter.place_market_order(close_side, lighter_filled_size)

            if close_result:
                print(f"✅ Lighterポジションクローズ完了")
            else:
                print(f"❌ Lighterポジションクローズ失敗 - MANUAL INTERVENTION REQUIRED!")
                await self.notifier.send_error(
                    "CRITICAL: Failed to close Lighter position after Paradex failure",
                    f"Lighter size: {lighter_filled_size}, Paradex error: {paradex_result}"
                )

            return {
                'success': False,
                'error': 'Paradex market order failed',
                'paradex': paradex_result,
                'lighter_closed': close_result
            }

        paradex_filled_size = await self._verify_filled_size(paradex_result, position_size, "Paradex")

        print(f"\n✅ Paradex約定完了!")
        print(f"   約定サイズ: {paradex_filled_size:.2f}")

        # Step 3: Check for size mismatch and apply hybrid adjustment if needed
        print(f"\n{'='*60}")
        print(f"STEP 3: ポジションサイズ確認")
        print(f"{'='*60}")
        print(f"   Paradex: {paradex_filled_size:.2f}")
        print(f"   Lighter: {lighter_filled_size:.2f}")
        print(f"   誤差: {abs(paradex_filled_size - lighter_filled_size):.2f}")

        target_size = position_size
        paradex_total_filled = paradex_filled_size
        lighter_total_filled = lighter_filled_size

        # Check if adjustment is needed (tolerance: 0.5 units or 1%)
        shortage_tolerance = max(0.5, target_size * 0.01)
        paradex_shortage = target_size - paradex_total_filled
        lighter_shortage = target_size - lighter_total_filled

        if abs(paradex_shortage) > shortage_tolerance or abs(lighter_shortage) > shortage_tolerance:
            print(f"\n⚠️  ポジション調整が必要")
            print(f"   Paradex不足: {paradex_shortage:.2f}")
            print(f"   Lighter不足: {lighter_shortage:.2f}")

            # Apply hybrid retry logic for adjustment
            MAX_RETRIES = 3

            for attempt in range(1, MAX_RETRIES + 1):
                print(f"\n{'='*60}")
                print(f"📍調整 Attempt {attempt}/{MAX_RETRIES}")
                print(f"{'='*60}")

                # Calculate remaining shortage
                paradex_shortage = target_size - paradex_total_filled
                lighter_shortage = target_size - lighter_total_filled

                # If both are filled, we're done
                if paradex_shortage <= 0.5 and lighter_shortage <= 0.5:  # Allow 0.5 unit tolerance
                    print(f"✅ Position fully filled!")
                    print(f"   Paradex: {paradex_total_filled:.2f}/{target_size:.2f}")
                    print(f"   Lighter: {lighter_total_filled:.2f}/{target_size:.2f}")
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
                print(f"   Paradex: {paradex_total_filled:.2f}/{target_size:.2f} ({paradex_total_filled/target_size*100:.1f}%)")
                print(f"   Lighter: {lighter_total_filled:.2f}/{target_size:.2f} ({lighter_total_filled/target_size*100:.1f}%)")

                # Check if we're close enough
                fill_tolerance = 0.99  # 99% fill is acceptable
                paradex_fill_ratio = paradex_total_filled / target_size
                lighter_fill_ratio = lighter_total_filled / target_size

                if paradex_fill_ratio >= fill_tolerance and lighter_fill_ratio >= fill_tolerance:
                    print(f"✅ Position sufficiently filled (>= {fill_tolerance*100:.0f}%)")
                    break

                # If this was the last attempt and we still have shortage, trigger emergency close
                if attempt == MAX_RETRIES:
                    print(f"\n⚠️  MAX RETRIES REACHED - Position not fully filled")
                    print(f"   Paradex filled: {paradex_total_filled:.2f}/{target_size:.2f}")
                    print(f"   Lighter filled: {lighter_total_filled:.2f}/{target_size:.2f}")

                    # Emergency: Close all positions and retry from scratch
                    if paradex_total_filled > 0 or lighter_total_filled > 0:
                        print(f"\n🚨 Triggering emergency closure...")

                        # Close whatever we managed to fill
                        close_size = max(paradex_total_filled, lighter_total_filled)
                        emergency_success = await self._emergency_close_all(close_size)

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
        paradex_success = paradex_total_filled >= target_size * 0.99
        lighter_success = lighter_total_filled >= target_size * 0.99

        # Check if both succeeded
        if paradex_success and lighter_success:
            # Use actual filled sizes
            actual_position_size = min(paradex_total_filled, lighter_total_filled)
            self.position_open = True
            self.current_position = {
                'timestamp': datetime.now().isoformat(),
                'size': actual_position_size,  # Use actual filled size
                'target_size': target_size,     # Original target
                'paradex_filled': paradex_total_filled,
                'lighter_filled': lighter_total_filled,
                'paradex_price': paradex_price,
                'lighter_price': lighter_price,
                'paradex_side': paradex_side,  # Save the side for closing
                'lighter_side': lighter_side,  # Save the side for closing
                'fill_ratio': min(paradex_total_filled/target_size, lighter_total_filled/target_size) * 100,
                'funding_check': funding_check,  # Save funding rate analysis
            }

            # Save position to file for emergency close
            self._save_position_to_file()

            print("\n" + "="*60)
            print("✅ Delta neutral position opened successfully!")
            print("="*60)
            print(f"   Target size: {target_size:.2f}")
            print(f"   Paradex filled: {paradex_total_filled:.2f} ({paradex_total_filled/target_size*100:.1f}%)")
            print(f"   Lighter filled: {lighter_total_filled:.2f} ({lighter_total_filled/target_size*100:.1f}%)")
            print(f"   Position size: {actual_position_size:.2f}")
            print("="*60)

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
        print(f"   Paradex fill: {paradex_total_filled:.2f}/{target_size:.2f}")
        print(f"   Lighter fill: {lighter_total_filled:.2f}/{target_size:.2f}")

        return {
            'success': False,
            'error': 'Insufficient fill after retries',
            'paradex_filled': paradex_total_filled,
            'lighter_filled': lighter_total_filled
        }

    async def close_delta_neutral_position(self) -> Dict[str, Any]:
        """
        Close delta neutral position by placing orders opposite to the opening sides

        The closing side is determined by what was opened:
        - If opened with BUY, close with SELL
        - If opened with SELL, close with BUY

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

        # Get the sides that were used when opening the position
        # To close, we use the opposite side
        opened_paradex_side = self.current_position.get('paradex_side', 'BUY')
        opened_lighter_side = self.current_position.get('lighter_side', 'SELL')

        # Determine closing sides (opposite of opening)
        close_paradex_side = 'SELL' if opened_paradex_side == 'BUY' else 'BUY'
        close_lighter_side = 'BUY' if opened_lighter_side == 'SELL' else 'SELL'

        print(f"   オープン時: Paradex {opened_paradex_side}, Lighter {opened_lighter_side}")
        print(f"   クローズ時: Paradex {close_paradex_side}, Lighter {close_lighter_side}")

        # Get and display current balances before closing
        print("\n💰 Checking current balances...")
        balances = await self.get_available_balance()
        paradex_balance = balances.get('paradex', 0)
        lighter_balance = balances.get('lighter', 0)

        print(f"   Paradex: ${paradex_balance:.2f}")
        print(f"   Lighter:  ${lighter_balance:.2f}")
        print(f"   Total:    ${paradex_balance + lighter_balance:.2f}")

        # ===== スプレッド監視機能（コメントアウト） =====
        # Get spread monitoring configuration
        # max_spread_pct = self.bot.config.spread_max_pct
        # check_interval = self.bot.config.spread_check_interval
        # timeout = self.bot.config.spread_check_timeout

        # Wait for tight spread before closing
        # price_result = await self._wait_for_tight_spread(max_spread_pct, check_interval, timeout)

        # if price_result is None:
        #     print("⚠️  Failed to achieve target spread within timeout for closing")
        #     print("   Using saved entry prices as reference...")
        #     # Use entry prices if spread timeout
        #     paradex_price = self.current_position.get('paradex_price', 0)
        #     lighter_price = self.current_position.get('lighter_price', 0)
        # else:
        #     paradex_price, lighter_price = price_result

        #     # Final check if prices are available
        #     if not paradex_price or not lighter_price:
        #         print("⚠️  Failed to fetch current prices for closing")
        #         print("   Using saved entry prices as reference...")
        #         # Use entry prices if current prices unavailable
        #         paradex_price = self.current_position.get('paradex_price', 0)
        #         lighter_price = self.current_position.get('lighter_price', 0)
        # ===== スプレッド監視機能ここまで =====

        # 直接価格を取得（スプレッド監視なし）
        print(f"\n💰 クローズ用の現在価格を取得中...")
        paradex_bid_ask = await self.bot.paradex.get_bid_ask()
        lighter_bid_ask = await self.bot.lighter.get_bid_ask()

        if not paradex_bid_ask or not lighter_bid_ask:
            print("⚠️  Failed to fetch current prices for closing")
            print("   Using saved entry prices as reference...")
            paradex_price = self.current_position.get('paradex_price', 0)
            lighter_price = self.current_position.get('lighter_price', 0)
        else:
            paradex_bid, paradex_ask = paradex_bid_ask
            lighter_bid, lighter_ask = lighter_bid_ask

            paradex_price = (paradex_bid + paradex_ask) / 2
            lighter_price = (lighter_bid + lighter_ask) / 2

            print(f"   Paradex: ${paradex_price:.4f} (Bid: ${paradex_bid:.4f}, Ask: ${paradex_ask:.4f})")
            print(f"   Lighter: ${lighter_price:.4f} (Bid: ${lighter_bid:.4f}, Ask: ${lighter_ask:.4f})")

        print(f"\n📊 Closing positions...")
        if paradex_price:
            print(f"   Paradex: {close_paradex_side} {position_size} @ ${paradex_price:.4f}")
        else:
            print(f"   Paradex: {close_paradex_side} {position_size} @ (price unavailable)")

        if lighter_price:
            print(f"   Lighter: {close_lighter_side} {position_size} @ ${lighter_price:.4f}")
        else:
            print(f"   Lighter: {close_lighter_side} {position_size} @ (price unavailable)")

        # Execute both orders simultaneously with reduce_only=True
        # reduce_only ensures orders only close existing positions, not open new ones
        tasks = [
            self.bot.paradex.place_market_order(close_paradex_side, position_size),
            self.bot.lighter.place_market_order(close_lighter_side, position_size, reduce_only=True)
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

        # If a position already exists at startup, close it first
        if self.position_open:
            print("\n⚠️  既存のポジションを先に決済します...")
            await self.close_delta_neutral_position()
            print("\n⏸️  Waiting 30 seconds before starting loop...")
            await asyncio.sleep(30)

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
                try:
                    await self.close_delta_neutral_position()
                except Exception as e:
                    print(f"❌ Error closing position: {e}")
                    print("⚠️  Manual intervention may be required")
            raise  # Re-raise to ensure proper cleanup
        except Exception as e:
            print(f"\n❌ Error in loop: {e}")
            await self.notifier.send_error(f"Loop error: {e}", "Bot stopped due to error")
            if self.position_open:
                print("🔄 Attempting to close position...")
                await self.close_delta_neutral_position()
            raise
