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
        Check if there's a funding rate arbitrage opportunity (Paradex-only strategy)

        Strategy:
        - Only check Paradex funding rate (simpler, more reliable)
        - If positive (>threshold): Paradex SHORT, Lighter LONG
        - If negative (<-threshold): Paradex LONG, Lighter SHORT
        - Lighter automatically hedges (delta neutral)

        For short-term holding (2-3 hours), Paradex continuous funding is more suitable

        Returns:
            Dict with funding rate analysis and recommendation:
            {
                'opportunity': bool,
                'paradex_rate': float,
                'paradex_rate_8h': float,
                'estimated_apy': float,
                'recommendation': str,
                'paradex_side': str,
                'lighter_side': str,
                'reason': str
            }
        """
        if not self.bot.config.funding_rate_enabled:
            return {
                'opportunity': True,  # Bypass check if disabled
                'paradex_rate': 0,
                'paradex_rate_8h': 0,
                'estimated_apy': 0,
                'recommendation': 'NO_CHECK',
                'paradex_side': 'BUY',  # Default
                'lighter_side': 'SELL',
                'reason': 'Funding rate check disabled in config'
            }

        print(f"\n💹 Paradexファンディングレートをチェック中...")

        try:
            # Get Paradex funding rate only
            paradex_funding = await self.bot.paradex.get_funding_rate()

            if not paradex_funding:
                print("⚠️  Paradexファンディングレート取得失敗、スキップします")
                return {
                    'opportunity': True,  # Proceed anyway
                    'paradex_rate': 0,
                    'paradex_rate_8h': 0,
                    'estimated_apy': 0,
                    'recommendation': 'DATA_UNAVAILABLE',
                    'paradex_side': 'BUY',  # Default
                    'lighter_side': 'SELL',
                    'reason': 'Could not fetch Paradex funding rate'
                }

            # Extract 8-hour rate
            paradex_rate_8h = paradex_funding['funding_rate']

            # Convert to percentage
            paradex_rate_pct = paradex_rate_8h * 100

            print(f"   Paradex: {paradex_rate_pct:.4f}%/8時間 (連続型)")

            # Estimate annual yield
            # 3 funding periods per day (8h each) × 365 days
            estimated_apy = paradex_rate_8h * 3 * 365 * 100

            print(f"   推定APY: {estimated_apy:.2f}%")

            # Check if funding rate is zero (no opportunity)
            if paradex_rate_8h == 0:
                print(f"   ⚠️  ファンディングレートがゼロ - 機会なし")
                return {
                    'opportunity': False,
                    'paradex_rate': paradex_rate_8h,
                    'paradex_rate_8h': paradex_rate_8h,
                    'estimated_apy': 0,
                    'recommendation': 'NO_POSITION',
                    'paradex_side': 'BUY',
                    'lighter_side': 'SELL',
                    'reason': 'Funding rate is zero'
                }

            # Determine position direction based on Paradex funding rate sign only
            # No threshold check - any non-zero rate creates an opportunity
            if paradex_rate_8h > 0:
                # Positive funding: longs pay shorts
                # → Paradex SHORT (receive funding)
                # → Lighter LONG (delta hedge)
                paradex_side = 'SELL'
                lighter_side = 'BUY'
                recommendation = 'PARADEX_SHORT_LIGHTER_LONG'
                reason = f'Paradex positive funding (+{paradex_rate_pct:.4f}%) → SHORT receives payment'
            else:
                # Negative funding: shorts pay longs
                # → Paradex LONG (receive funding)
                # → Lighter SHORT (delta hedge)
                paradex_side = 'BUY'
                lighter_side = 'SELL'
                recommendation = 'PARADEX_LONG_LIGHTER_SHORT'
                reason = f'Paradex negative funding ({paradex_rate_pct:.4f}%) → LONG receives payment'

            print(f"   ✅ 機会あり: {recommendation}")
            print(f"   理由: {reason}")
            print(f"   Paradex: {paradex_side}, Lighter: {lighter_side} (ヘッジ)")

            return {
                'opportunity': True,
                'paradex_rate': paradex_rate_8h,
                'paradex_rate_8h': paradex_rate_8h,
                'estimated_apy': estimated_apy,
                'recommendation': recommendation,
                'paradex_side': paradex_side,
                'lighter_side': lighter_side,
                'reason': reason
            }

        except Exception as e:
            print(f"❌ Paradexファンディングレートチェックエラー: {e}")
            import traceback
            traceback.print_exc()
            return {
                'opportunity': True,  # Proceed anyway on error
                'paradex_rate': 0,
                'paradex_rate_8h': 0,
                'estimated_apy': 0,
                'recommendation': 'ERROR',
                'paradex_side': 'BUY',  # Default
                'lighter_side': 'SELL',
                'reason': f'Error checking Paradex funding rate: {e}'
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

    async def get_available_balance(self, silent: bool = False) -> Dict[str, float]:
        """
        Get available balances from both exchanges

        Args:
            silent: If True, suppress output (default: False)

        Returns:
            Dictionary with balances for each exchange
        """
        if not silent:
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

        if not silent:
            print(f"   Paradex: ${paradex_balance:.2f}")
            print(f"   Lighter: ${lighter_balance:.2f}")

        return balances


    async def _cancel_all_pending_orders(self, all_order_ids: list, filled_order_id: str = None) -> None:
        """
        Cancel ALL pending orders using cancel_all_orders() API

        This uses the SDK's cancel_all_orders method to ensure ALL unfilled orders
        are cancelled. The filled_order_id parameter is ignored since filled orders
        are automatically excluded (they are no longer pending).

        Args:
            all_order_ids: List of all order IDs that were placed (for logging only)
            filled_order_id: Order ID that was filled (ignored, kept for compatibility)
        """
        print(f"\n🗑️  全未約定注文をキャンセル中（cancel_all_orders使用）...")

        try:
            success = await self.bot.lighter.cancel_all_orders()
            if success:
                print(f"   ✅ 全注文キャンセル完了")
            else:
                print(f"   ⚠️  全注文キャンセル失敗")
        except Exception as e:
            print(f"   ❌ キャンセルエラー: {e}")

    async def _poll_for_position_fill(self, target_size: float, timeout: int = 30) -> bool:
        """
        Poll for position fill by checking position size via REST API

        Args:
            target_size: Expected position size after fill
            timeout: Maximum wait time in seconds

        Returns:
            True if filled (position reached target), False if timeout
        """
        polling_interval = 2.0  # 2秒間隔でポーリング（より確実な検知）
        max_attempts = int(timeout / polling_interval)

        print(f"   📊 ポーリング開始: 目標ポジション {target_size:.2f}")
        print(f"   ⏱️  間隔: {polling_interval}秒, 最大試行: {max_attempts}回")

        for attempt in range(1, max_attempts + 1):
            try:
                # REST APIでアカウント情報を取得
                account_data = await self.bot.lighter.get_account_balance()

                if account_data and account_data.get('status') not in ['SDK_REQUIRED', 'UNAVAILABLE']:
                    # ポジション情報を抽出
                    position = await self.bot.lighter.get_position_from_account(account_data)

                    if position:
                        current_size = position.get('size', 0)

                        # 進捗表示（毎回表示）
                        remaining_attempts = max_attempts - attempt
                        print(f"\r   📈 試行 {attempt}/{max_attempts}: ポジション {current_size:.2f} → 目標 {target_size:.2f} (残り {remaining_attempts}回)", end='', flush=True)

                        # 目標サイズに到達したか確認（0.01の誤差許容）
                        if abs(current_size - target_size) < 0.01:
                            print(f"\n   ✅ 約定確認！ポジション: {current_size:.2f} (試行回数: {attempt})")
                            return True
                    else:
                        # ポジションが見つからない場合（初回注文など）
                        print(f"\r   ⏳ 試行 {attempt}/{max_attempts}: ポジション取得中... (残り {max_attempts - attempt}回)", end='', flush=True)
                else:
                    # SDK必須または利用不可の場合
                    if attempt == 1:
                        print(f"\n   ⚠️  アカウント情報の取得に失敗: {account_data.get('status', 'UNKNOWN')}")
                        print(f"   単純待機にフォールバック（{timeout}秒）...")
                        await asyncio.sleep(timeout)
                        return True  # 楽観的に成功とみなす

            except Exception as e:
                # エラー表示（毎回）
                print(f"\r   ⚠️  試行 {attempt}: ポジション確認エラー: {str(e)[:50]}", end='', flush=True)

            # 次のポーリングまで待機
            await asyncio.sleep(polling_interval)

        # メインループがタイムアウト → 最終確認を実行
        print(f"\n\n   ⚠️  メインポーリングがタイムアウト - 最終確認を開始します...")
        print(f"   💡 API同期遅延の可能性があるため、追加で3回確認します")

        for final_check in range(1, 4):
            try:
                # 少し長めに待機してからチェック（API同期を待つ）
                await asyncio.sleep(2)

                print(f"\n   🔍 最終確認 {final_check}/3...")
                account_data = await self.bot.lighter.get_account_balance()

                if account_data and account_data.get('status') not in ['SDK_REQUIRED', 'UNAVAILABLE']:
                    position = await self.bot.lighter.get_position_from_account(account_data)

                    if position:
                        current_size = position.get('size', 0)
                        print(f"      現在のポジション: {current_size:.2f}, 目標: {target_size:.2f}")

                        # 約定確認
                        if abs(current_size - target_size) < 0.01:
                            print(f"\n   ✅✅ 【最終確認で約定検知！】ポジション: {current_size:.2f}")
                            print(f"      API同期遅延により初回ポーリングでは検知できませんでした")
                            return True
                    else:
                        print(f"      ポジション情報なし")
                else:
                    print(f"      アカウント情報取得失敗: {account_data.get('status', 'UNKNOWN') if account_data else 'None'}")

            except Exception as e:
                print(f"      ⚠️  エラー: {str(e)[:80]}")

        # 最終確認でも検知できなかった
        print(f"\n   ❌ タイムアウト: 最終確認({final_check}回)でも約定を確認できませんでした")
        print(f"      総確認時間: {timeout}秒 + 追加6秒 = {timeout + 6}秒")
        return False

    async def _wait_for_lighter_fill_via_websocket(self, initial_position_size: float, target_size: float, timeout: int = 30) -> bool:
        """
        Wait for order to fill by monitoring position changes via WebSocket

        NOTE: WebSocket should be already connected BEFORE calling this method

        Args:
            initial_position_size: Position size before order (not used in WebSocket mode)
            target_size: Expected position size after fill
            timeout: Maximum wait time in seconds

        Returns:
            True if filled, False if timeout
        """
        try:
            # Verify WebSocket is running
            if not self.bot.lighter._ws_running:
                print(f"   ⚠️  WebSocket未接続 - REST APIポーリングにフォールバック")
                return await self._poll_for_position_fill(target_size, timeout)

            print(f"\n📊 WebSocketで約定監視中...")
            print(f"   目標ポジション: {target_size:.2f}")
            print(f"   タイムアウト: {timeout}秒")

            filled_event = asyncio.Event()

            async def on_position_fill(account_data: dict = None, *args, **kwargs):
                """Callback for account updates from WebSocket

                Accepts variable arguments for SDK compatibility
                """
                try:
                    # Handle different argument patterns
                    if account_data is None and len(args) > 0:
                        account_data = args[0]
                    elif account_data is None and 'account_data' in kwargs:
                        account_data = kwargs['account_data']

                    if not account_data:
                        return

                    position = await self.bot.lighter.get_position_from_account(account_data)
                    if position:
                        current_size = position.get('size', 0)
                        print(f"\r   📊 [WebSocket] ポジション: {current_size:.2f} → 目標: {target_size:.2f}", end='', flush=True)

                        # Check if target reached
                        if abs(current_size - target_size) < 0.01:  # Allow small tolerance
                            print(f"\n   ✅ [WebSocket] 約定確認！ポジション: {current_size:.2f}")
                            filled_event.set()
                except Exception as e:
                    print(f"\n   ⚠️  [WebSocket] アカウント更新処理エラー: {e}")

            # Register callback to existing WebSocket connection
            self.bot.lighter.add_position_update_callback(on_position_fill)

            try:
                # Wait for fill or timeout
                await asyncio.wait_for(filled_event.wait(), timeout=timeout)
                print(f"\n   ✅ WebSocketで約定を検知しました！")
                return True

            except asyncio.TimeoutError:
                print(f"\n   ⏰ [WebSocket] タイムアウト - 最終確認を実行中...")

                # Final verification with polling
                final_result = await self._poll_for_position_fill(target_size, timeout=6)
                if final_result:
                    print(f"   ✅ 最終確認で約定を検知！")
                    return True
                else:
                    print(f"   ❌ タイムアウト: {timeout}秒以内に約定を確認できませんでした")
                    return False

            finally:
                # Remove callback after monitoring completes
                self.bot.lighter.remove_position_update_callback(on_position_fill)

        except Exception as e:
            # Unexpected error - fallback to polling
            print(f"\n   ❌ WebSocket監視エラー: {e}")
            print(f"   エラータイプ: {type(e).__name__}")
            print(f"   REST API ポーリング方式にフォールバック...")
            return await self._poll_for_position_fill(target_size, timeout)

    async def _check_position_closed(self, initial_position_size: float, expected_reduction: float, timeout: int = 30, side: str = 'SELL') -> bool:
        """
        Check if CLOSE order (reduce_only) has filled by verifying position is gone/reduced

        LOGIC FOR CLOSE ORDERS:
        - Position still exists = Order NOT filled → Return False
        - Position gone/reduced = Order filled → Return True

        This is the OPPOSITE of open orders!

        Args:
            initial_position_size: Position size before close order
            expected_reduction: Size of the position to close
            timeout: Maximum wait time in seconds
            side: Order side ('BUY' closes short, 'SELL' closes long)

        Returns:
            True if position closed (order filled), False if position still exists (unfilled)
        """
        polling_interval = 2.0  # 2秒間隔でポーリング
        max_attempts = int(timeout / polling_interval)

        print(f"   📊 決済確認ポーリング開始")
        print(f"   初期ポジション: {initial_position_size:.2f}")
        print(f"   決済サイズ: {expected_reduction:.2f}")
        print(f"   期待値: ポジションが消失または {abs(initial_position_size) - expected_reduction:.2f} に減少")
        print(f"   ⏱️  間隔: {polling_interval}秒, 最大試行: {max_attempts}回")

        for attempt in range(1, max_attempts + 1):
            try:
                # REST APIでアカウント情報を取得
                account_data = await self.bot.lighter.get_account_balance()

                if account_data and account_data.get('status') not in ['SDK_REQUIRED', 'UNAVAILABLE']:
                    # ポジション情報を抽出
                    position = await self.bot.lighter.get_position_from_account(account_data)

                    if position:
                        current_size = position.get('size', 0)
                        remaining_attempts = max_attempts - attempt

                        print(f"\r   📈 試行 {attempt}/{max_attempts}: ポジション {current_size:.2f} (初期: {initial_position_size:.2f}) 残り {remaining_attempts}回", end='', flush=True)

                        # CRITICAL: For close orders, check if position is REDUCED or GONE
                        # Allow 10% tolerance
                        tolerance = expected_reduction * 0.1
                        actual_reduction = abs(initial_position_size) - abs(current_size)

                        if actual_reduction >= (expected_reduction - tolerance):
                            print(f"\n   ✅ 約定確認！ポジションが減少しました")
                            print(f"      初期: {initial_position_size:.2f} → 現在: {current_size:.2f}")
                            print(f"      減少量: {actual_reduction:.2f} (期待: {expected_reduction:.2f})")
                            return True
                        elif abs(current_size) < 0.01:
                            # Position is essentially zero (fully closed)
                            print(f"\n   ✅ 約定確認！ポジションが完全にクローズされました")
                            print(f"      初期: {initial_position_size:.2f} → 現在: {current_size:.2f}")
                            return True
                    else:
                        # No position found = fully closed
                        print(f"\n   ✅ 約定確認！ポジションが見つかりません（完全クローズ）")
                        return True
                else:
                    # SDK必須または利用不可の場合
                    if attempt == 1:
                        print(f"\n   ⚠️  アカウント情報の取得に失敗: {account_data.get('status', 'UNKNOWN')}")
                        print(f"   単純待機にフォールバック（{timeout}秒）...")
                        await asyncio.sleep(timeout)
                        return True  # 楽観的に成功とみなす

            except Exception as e:
                print(f"\r   ⚠️  試行 {attempt}: ポジション確認エラー: {str(e)[:50]}", end='', flush=True)

            # 次のポーリングまで待機
            await asyncio.sleep(polling_interval)

        # タイムアウト → 最終確認
        print(f"\n\n   ⚠️  メインポーリングがタイムアウト - 最終確認を開始します...")
        print(f"   💡 API同期遅延の可能性があるため、追加で3回確認します")

        for final_check in range(1, 4):
            try:
                await asyncio.sleep(2)
                print(f"\n   🔍 最終確認 {final_check}/3...")
                account_data = await self.bot.lighter.get_account_balance()

                if account_data and account_data.get('status') not in ['SDK_REQUIRED', 'UNAVAILABLE']:
                    position = await self.bot.lighter.get_position_from_account(account_data)

                    if position:
                        current_size = position.get('size', 0)
                        print(f"      現在のポジション: {current_size:.2f}, 初期: {initial_position_size:.2f}")

                        # Check if reduced
                        tolerance = expected_reduction * 0.1
                        actual_reduction = abs(initial_position_size) - abs(current_size)

                        if actual_reduction >= (expected_reduction - tolerance) or abs(current_size) < 0.01:
                            print(f"\n   ✅✅ 【最終確認で約定検知！】")
                            print(f"      初期: {initial_position_size:.2f} → 現在: {current_size:.2f}")
                            print(f"      API同期遅延により初回ポーリングでは検知できませんでした")
                            return True
                        else:
                            print(f"      ⚠️  ポジションがまだ残っています（減少: {actual_reduction:.2f} < 期待: {expected_reduction:.2f}）")
                    else:
                        print(f"      ✅ ポジション情報なし - 完全クローズされました")
                        return True
                else:
                    print(f"      アカウント情報取得失敗: {account_data.get('status', 'UNKNOWN') if account_data else 'None'}")

            except Exception as e:
                print(f"      ⚠️  エラー: {str(e)[:80]}")

        # 最終確認でも約定を確認できなかった = ポジションがまだ存在 = 未約定
        print(f"\n   ❌ タイムアウト: ポジションがまだ存在しています - 未約定と判断")
        print(f"      総確認時間: {timeout}秒 + 追加6秒 = {timeout + 6}秒")
        return False

    async def _place_lighter_limit_with_price_update(self, side: str, size: float, max_attempts: int = 12, wait_seconds: int = 15, use_websocket: bool = True, reduce_only: bool = False) -> Optional[Dict[str, Any]]:
        """
        Place Lighter limit order with price updates until filled

        Args:
            side: Order side ('BUY' or 'SELL')
            size: Order size
            max_attempts: Maximum number of attempts (default: 12)
            wait_seconds: Seconds to wait between attempts (default: 5)
            use_websocket: Use WebSocket for fill detection (default: True)
            reduce_only: If True, order only closes existing position (default: False)

        Returns:
            Order result if filled, None if failed
        """
        print(f"\n📍 Lighter指値注文（価格自動更新）")
        print(f"   注文方向: {side}")
        print(f"   目標サイズ: {size:.2f}")
        print(f"   最大試行回数: {max_attempts}")
        print(f"   更新間隔: {wait_seconds}秒")
        print(f"   WebSocket検知: {'有効' if use_websocket else '無効'}")
        print(f"   Reduce Only: {'有効' if reduce_only else '無効'}")

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

        # CRITICAL: Start WebSocket BEFORE placing any orders
        if use_websocket:
            print(f"\n🔌 【重要】注文前にWebSocket接続を確立中...")
            ws_started = await self.bot.lighter.start_websocket()
            if ws_started:
                print(f"   ✅ WebSocket接続完了 - 約定をリアルタイム監視できます")
            else:
                print(f"   ⚠️  WebSocket接続失敗 - REST APIポーリングにフォールバック")
                use_websocket = False

        for attempt in range(1, max_attempts + 1):
            print(f"\n{'='*60}")
            print(f"🔄 試行 {attempt}/{max_attempts}")
            print(f"{'='*60}")

            # STEP 0: Update current position size (CRITICAL for detecting fills from previous attempts)
            if attempt > 1:
                try:
                    account_data = await self.bot.lighter.get_account_balance()
                    if account_data:
                        position = await self.bot.lighter.get_position_from_account(account_data)
                        if position:
                            current_pos_size = position.get('size', 0)
                            print(f"   📊 現在のポジション: {current_pos_size:.2f}")

                            # Check if target already reached (previous order filled)
                            expected_position = initial_position_size + (-size if side == 'SELL' else size)
                            if abs(current_pos_size - expected_position) < size * 0.15:  # 15% tolerance
                                print(f"   ✅ 前回の注文が約定していました！")
                                print(f"   初期: {initial_position_size:.2f} → 現在: {current_pos_size:.2f} (期待: {expected_position:.2f})")

                                # Cancel any pending orders
                                await self._cancel_all_pending_orders(all_order_ids)

                                return {
                                    'order_id': all_order_ids[-1] if all_order_ids else 'detected',
                                    'tx_hash': 'detected',
                                    'filled_size': size,
                                    'filled_price': 0,  # Unknown
                                    'status': 'FILLED'
                                }
                            else:
                                print(f"   ⚠️  ポジション未変化 - 約定していません")
                                print(f"   初期: {initial_position_size:.2f} → 現在: {current_pos_size:.2f} (期待: {expected_position:.2f})")
                        else:
                            print(f"   📊 現在のポジション: なし (0)")
                except Exception as e:
                    print(f"   ⚠️  ポジション確認エラー: {e}")

            # STEP 1: CRITICAL - Cancel ALL orders using cancel_all_orders() API
            # This is MANDATORY to prevent multiple orders from filling simultaneously
            if all_order_ids or attempt > 1:
                # Use cancel_all_orders for guaranteed cancellation of ALL pending orders
                print(f"   🗑️  【CRITICAL】全未約定注文を一括キャンセル中（SDK cancel_all_orders使用）")

                success = await self.bot.lighter.cancel_all_orders()

                if not success:
                    print(f"   ❌ 全注文キャンセル失敗 - 続行を中止します")
                    return None

                # CRITICAL: Verify ALL orders are cancelled on-chain
                print(f"   🔍 【重要】キャンセル確認中... (オンチェーン検証)")
                max_verify_attempts = 10
                for verify_attempt in range(1, max_verify_attempts + 1):
                    try:
                        open_orders = await self.bot.lighter.get_open_orders()

                        if not open_orders:
                            print(f"   ✅ キャンセル確認完了 - すべての注文が確実にキャンセルされました")
                            break

                        if verify_attempt < max_verify_attempts:
                            print(f"   ⏳ 試行 {verify_attempt}/{max_verify_attempts}: まだ {len(open_orders)}個の注文が残っています... 1秒後に再確認")
                            await asyncio.sleep(1.0)
                        else:
                            print(f"   ❌ エラー: {len(open_orders)}個の注文が残っています - 続行を中止します")
                            print(f"   残存注文ID: {open_orders}")
                            return None  # ABORT - Do not place new order if old orders still exist
                    except Exception as e:
                        print(f"   ⚠️  確認エラー (試行{verify_attempt}): {e}")
                        if verify_attempt < max_verify_attempts:
                            await asyncio.sleep(1.0)

                all_order_ids.clear()  # Clear the list after cancellation
                current_order_id = None
                await asyncio.sleep(1.0)  # Wait 1 second before placing new order

            # STEP 2: Get latest bid/ask
            print(f"   📊 最新価格を取得中...")
            try:
                bid_ask = await asyncio.wait_for(
                    self.bot.lighter.get_bid_ask(),
                    timeout=30.0  # 30 second timeout for price fetch
                )
            except asyncio.TimeoutError:
                print(f"   ❌ 価格取得タイムアウト (30秒) - {wait_seconds}秒後に再試行...")
                await asyncio.sleep(wait_seconds)
                continue

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

            # STEP 3: Pre-order safety check - verify NO open orders exist
            print(f"   🔒 【安全確認】注文前の最終チェック...")
            try:
                final_check_orders = await self.bot.lighter.get_open_orders()
                if final_check_orders:
                    print(f"   ⚠️  警告: {len(final_check_orders)}個の未約定注文が検出されました")
                    print(f"   注文ID: {final_check_orders}")
                    print(f"   🗑️  これらの注文を一括キャンセルします（cancel_all_orders使用）...")

                    # Use cancel_all_orders for guaranteed cancellation
                    success = await self.bot.lighter.cancel_all_orders()
                    if not success:
                        print(f"   ❌ 全注文キャンセル失敗 - この試行をスキップします")
                        await asyncio.sleep(wait_seconds)
                        continue

                    # Wait and re-verify
                    await asyncio.sleep(2.0)
                    recheck_orders = await self.bot.lighter.get_open_orders()
                    if recheck_orders:
                        print(f"   ❌ エラー: まだ {len(recheck_orders)}個の注文が残っています - この試行をスキップします")
                        await asyncio.sleep(wait_seconds)
                        continue
                    else:
                        print(f"   ✅ 全注文キャンセル確認完了")
                else:
                    print(f"   ✅ 安全確認完了 - 未約定注文なし")
            except Exception as e:
                print(f"   ⚠️  安全確認エラー: {e} - 続行します")

            # STEP 4: Place new limit order
            print(f"   📝 注文を送信中...")
            try:
                order_result = await asyncio.wait_for(
                    self.bot.lighter.place_limit_order(side, size, limit_price, reduce_only=reduce_only),
                    timeout=30.0  # 30 second timeout for order placement
                )
            except asyncio.TimeoutError:
                print(f"   ❌ 注文送信タイムアウト (30秒) - {wait_seconds}秒後に再試行...")
                await asyncio.sleep(wait_seconds)
                continue

            if not order_result:
                print("❌ 注文失敗")
                await asyncio.sleep(wait_seconds)
                continue

            current_order_id = order_result.get('order_id')
            tx_hash = order_result.get('tx_hash')
            all_order_ids.append(current_order_id)  # Track this order

            print(f"   ✓ 注文送信完了")
            print(f"   Order ID: {current_order_id}")
            print(f"   TX Hash: {tx_hash}")

            # CRITICAL: Different fill detection logic for OPEN vs CLOSE orders
            if reduce_only:
                # CLOSE ORDER: Check if position is gone (filled) or still exists (unfilled)
                print(f"   🔍 決済注文の約定確認中...")
                print(f"   ℹ️  ロジック: ポジション消失 = 約定 | ポジション存在 = 未約定")

                filled = await self._check_position_closed(
                    initial_position_size=initial_position_size,
                    expected_reduction=size,
                    timeout=wait_seconds,
                    side=side
                )

                if filled:
                    print(f"   ✅ 決済注文約定完了！ポジションがクローズされました")
                    # Cancel all other pending orders
                    await self._cancel_all_pending_orders(all_order_ids, current_order_id)
                    return {
                        **order_result,
                        'filled_size': size,
                        'filled_price': limit_price,
                        'status': 'FILLED'
                    }
                else:
                    print(f"   ⚠️  ポジションがまだ存在 = 未約定")
            else:
                # OPEN ORDER: Check if position increased (filled)
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
                        print(f"   ✅ 新規注文約定完了！")
                        # Cancel all other pending orders
                        await self._cancel_all_pending_orders(all_order_ids, current_order_id)
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
                        print(f"   ✅ 新規注文約定完了！")
                        # Cancel all other pending orders
                        await self._cancel_all_pending_orders(all_order_ids, current_order_id)
                        return {
                            **order_result,
                            'filled_size': size,
                            'filled_price': limit_price,
                            'status': 'FILLED'
                        }

            # 約定未確認 - current_order_idを保持して次のループで確実にキャンセル
            print(f"   ⚠️  約定未確認 - 次のループで前の注文をキャンセルして再試行...")

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

        # Get current prices for position opening
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
            wait_seconds=15,  # CRITICAL: 約定確認のタイムアウト時間（API同期遅延を考慮して15秒、複数注文約定を防止）
            use_websocket=self.bot.config.lighter_use_websocket
        )

        if not lighter_result:
            print(f"\n❌ Lighter注文失敗 - ポジションオープン中止")
            return {
                'success': False,
                'error': 'Lighter limit order failed after max attempts'
            }

        # CRITICAL: Verify Lighter order is actually FILLED before proceeding to Paradex
        lighter_status = lighter_result.get('status', '')
        if lighter_status != 'FILLED':
            print(f"\n❌ Lighter注文が約定していません - ステータス: {lighter_status}")
            await self.notifier.send_error(
                "CRITICAL: Lighter order not filled during open",
                f"Lighter order status: {lighter_status}, cannot proceed to Paradex"
            )
            return {
                'success': False,
                'error': f'Lighter order not filled (status: {lighter_status})'
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

        # CRITICAL: Verify actual positions exist before attempting to close
        print(f"\n🔍 実際のポジション状態を確認中...")

        # Check Lighter position with timeout
        print(f"   📡 Lighterアカウント情報を取得中...")
        try:
            lighter_account = await asyncio.wait_for(
                self.bot.lighter.get_account_balance(timeout=30.0),
                timeout=35.0  # Slightly longer than get_account_balance's internal timeout
            )
            print(f"   ✓ Lighterアカウント情報取得完了")
        except asyncio.TimeoutError:
            print(f"   ❌ Lighterアカウント情報取得タイムアウト (35秒)")
            return {
                'success': False,
                'error': 'Lighter account balance timeout',
                'action': 'Failed to verify position - API timeout'
            }

        lighter_position = await self.bot.lighter.get_position_from_account(lighter_account) if lighter_account else None

        if not lighter_position:
            print(f"⚠️  警告: Lighterに実際のポジションが存在しません！")
            print(f"   ファイルに保存されているポジション: {position_size}")
            print(f"   実際のLighterポジション: 0")
            print(f"   → ポジション情報をクリアして、新規オープンから開始します")

            # Clear stale position data
            self.position_open = False
            self.current_position = None
            self._save_position_to_file()

            return {
                'success': False,
                'error': 'No actual position found on Lighter',
                'action': 'Position data cleared - ready for new position'
            }

        actual_lighter_size = lighter_position.get('size', 0)
        print(f"   ✓ Lighterポジション確認: {actual_lighter_size:.2f}")

        # Use actual size instead of saved size if they differ
        if abs(actual_lighter_size - position_size) > 1:
            print(f"   ⚠️  保存されたサイズ({position_size})と実際のサイズ({actual_lighter_size:.2f})が異なります")
            print(f"   → 実際のサイズを使用します: {actual_lighter_size:.2f}")
            position_size = abs(actual_lighter_size)

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

        # Get current prices for position closing
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
        print(f"   Target size: {position_size}")

        # Step 1: Place Lighter limit order with price updates (with reduce_only=True)
        print(f"\n{'='*60}")
        print(f"STEP 1: Lighter指値注文（クローズ）- {close_lighter_side}")
        print(f"{'='*60}")

        lighter_result = await self._place_lighter_limit_with_price_update(
            side=close_lighter_side,
            size=position_size,
            max_attempts=12,
            wait_seconds=15,  # CRITICAL: 約定確認のタイムアウト時間（API同期遅延を考慮して15秒）
            use_websocket=self.bot.config.lighter_use_websocket,
            reduce_only=True  # Important: only close existing position
        )

        if not lighter_result:
            print(f"\n❌ Lighter注文失敗 - ポジションクローズ失敗")
            print(f"   ⚠️  実際のポジション状態を確認して状態をクリアします...")

            # Check actual Lighter position to determine if we should clear the flag
            try:
                lighter_account = await self.bot.lighter.get_account_balance()
                lighter_position = await self.bot.lighter.get_position_from_account(lighter_account) if lighter_account else None

                if not lighter_position:
                    print(f"   ✓ Lighterポジションなし - 状態をクリア")
                    self.position_open = False
                    self.current_position = None
                    self._remove_position_file()
                else:
                    print(f"   ⚠️  Lighterポジション残存: {lighter_position.get('size', 0)}")
            except Exception as e:
                print(f"   ⚠️  ポジション確認エラー: {e}")

            await self.notifier.send_error(
                "Failed to close Lighter position",
                f"Lighter {close_lighter_side} order failed after max attempts"
            )
            return {
                'success': False,
                'error': 'Lighter limit order failed during close'
            }

        # CRITICAL: Verify Lighter order is actually FILLED before proceeding to Paradex
        lighter_status = lighter_result.get('status', '')
        if lighter_status != 'FILLED':
            print(f"\n❌ Lighter注文が約定していません - ステータス: {lighter_status}")
            print(f"   ⚠️  実際のポジション状態を確認して状態をクリアします...")

            # Check actual Lighter position
            try:
                lighter_account = await self.bot.lighter.get_account_balance()
                lighter_position = await self.bot.lighter.get_position_from_account(lighter_account) if lighter_account else None

                if not lighter_position:
                    print(f"   ✓ Lighterポジションなし - 状態をクリア")
                    self.position_open = False
                    self.current_position = None
                    self._remove_position_file()
                else:
                    print(f"   ⚠️  Lighterポジション残存: {lighter_position.get('size', 0)}")
            except Exception as e:
                print(f"   ⚠️  ポジション確認エラー: {e}")

            await self.notifier.send_error(
                "CRITICAL: Lighter order not filled during close",
                f"Lighter order status: {lighter_status}, cannot proceed to Paradex"
            )
            return {
                'success': False,
                'error': f'Lighter order not filled (status: {lighter_status})'
            }

        lighter_filled_size = lighter_result.get('filled_size', position_size)
        lighter_filled_price = lighter_result.get('filled_price', lighter_price)

        print(f"\n✅ Lighter約定完了!")
        print(f"   約定サイズ: {lighter_filled_size:.2f}")
        print(f"   約定価格: ${lighter_filled_price:.4f}")

        # Step 2: Place Paradex market order to close
        print(f"\n{'='*60}")
        print(f"STEP 2: Paradex成り行き注文（クローズ）- {close_paradex_side}")
        print(f"{'='*60}")
        print(f"   {close_paradex_side} {position_size} @ market")

        paradex_result = await self.bot.paradex.place_market_order(close_paradex_side, position_size)

        if not paradex_result or isinstance(paradex_result, Exception):
            print(f"\n❌ Paradex注文失敗 - クローズ完了できませんでした")
            print(f"   ⚠️  Lighterは正常クローズ済み - 状態をクリアします")

            # Lighter is closed, so we should clear the position flag
            # even though Paradex failed
            self.position_open = False
            self.current_position = None
            self._remove_position_file()

            await self.notifier.send_error(
                "CRITICAL: Failed to close Paradex position",
                f"Lighter closed successfully but Paradex failed: {paradex_result}"
            )
            return {
                'success': False,
                'error': 'Paradex market order failed during close',
                'paradex': paradex_result,
                'lighter': lighter_result
            }

        paradex_filled_size = await self._verify_filled_size(paradex_result, position_size, "Paradex")

        print(f"\n✅ Paradex約定完了!")
        print(f"   約定サイズ: {paradex_filled_size:.2f}")

        # Calculate P&L using actual filled prices and sizes
        success = True
        if success:
            entry_paradex_price = self.current_position['paradex_price']
            entry_lighter_price = self.current_position['lighter_price']

            # Use actual filled prices for exit
            exit_paradex_price = paradex_price if paradex_price else entry_paradex_price
            exit_lighter_price = lighter_filled_price

            # Calculate P&L based on position direction
            if opened_paradex_side == 'BUY':
                # LONG position: profit = (exit - entry) * size
                paradex_pnl = (exit_paradex_price - entry_paradex_price) * paradex_filled_size
            else:
                # SHORT position: profit = (entry - exit) * size
                paradex_pnl = (entry_paradex_price - exit_paradex_price) * paradex_filled_size

            if opened_lighter_side == 'BUY':
                # LONG position: profit = (exit - entry) * size
                lighter_pnl = (exit_lighter_price - entry_lighter_price) * lighter_filled_size
            else:
                # SHORT position: profit = (entry - exit) * size
                lighter_pnl = (entry_lighter_price - exit_lighter_price) * lighter_filled_size

            total_pnl = paradex_pnl + lighter_pnl

            print(f"\n💵 P&L Summary:")
            print(f"   Paradex ({opened_paradex_side}): ${paradex_pnl:.2f}")
            print(f"   Lighter ({opened_lighter_side}): ${lighter_pnl:.2f}")
            print(f"   Total P&L: ${total_pnl:.2f}")

            # Save to history with actual filled prices and sizes
            trade_data = {
                'entry_time': self.current_position['timestamp'],
                'exit_time': datetime.now().isoformat(),
                'size': position_size,
                'paradex_filled_size': paradex_filled_size,
                'lighter_filled_size': lighter_filled_size,
                'paradex_entry_price': entry_paradex_price,
                'paradex_exit_price': exit_paradex_price,
                'lighter_entry_price': entry_lighter_price,
                'lighter_exit_price': exit_lighter_price,
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

        # CRITICAL: Check for actual positions on exchanges at startup
        # This prevents infinite retry loops if position_state.json is missing
        print("\n🔍 起動時チェック: 実際のポジションを確認中...")
        try:
            # Check Lighter position
            print(f"   📡 Lighterポジションチェック中...")
            lighter_account = await asyncio.wait_for(
                self.bot.lighter.get_account_balance(timeout=30.0),
                timeout=35.0
            )
            lighter_position = await self.bot.lighter.get_position_from_account(lighter_account) if lighter_account else None

            if lighter_position:
                lighter_size = lighter_position.get('size', 0)
                if abs(lighter_size) > 0.1:
                    print(f"   ⚠️  検出: Lighterポジション {lighter_size:.2f}")

                    # If position_open is False but actual position exists, restore state
                    if not self.position_open:
                        print(f"   🔧 ポジション状態を復元中...")
                        self.position_open = True
                        self.current_position = {
                            'size': abs(lighter_size),
                            'paradex_side': 'BUY',  # Assume standard strategy
                            'lighter_side': 'SELL',
                            'open_time': datetime.now().isoformat()
                        }
                        self._save_position_to_file()
                        print(f"   ✅ ポジション状態を復元しました")

            # Check Paradex position
            print(f"   📡 Paradexポジションチェック中...")
            paradex_account = await self.bot.paradex.get_account_balance()
            if paradex_account and hasattr(paradex_account, 'positions') and paradex_account.positions:
                for pos in paradex_account.positions:
                    if pos.market == self.bot.config.paradex_market:
                        paradex_size = float(pos.size)
                        if abs(paradex_size) > 0.1:
                            print(f"   ⚠️  検出: Paradexポジション {paradex_size:.2f}")

                            # If position_open is False but actual position exists, restore state
                            if not self.position_open:
                                print(f"   🔧 ポジション状態を復元中...")
                                self.position_open = True
                                self.current_position = {
                                    'size': abs(paradex_size),
                                    'paradex_side': 'BUY' if paradex_size > 0 else 'SELL',
                                    'lighter_side': 'SELL' if paradex_size > 0 else 'BUY',
                                    'open_time': datetime.now().isoformat()
                                }
                                self._save_position_to_file()
                                print(f"   ✅ ポジション状態を復元しました")
                        break
        except Exception as e:
            print(f"   ⚠️  起動時チェックエラー: {e}")

        print(f"   現在の状態: position_open={self.position_open}")

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

                # Check balances and send alert if low (silent to reduce output)
                try:
                    balances = await self.get_available_balance(silent=True)
                    await self.notifier.check_and_alert_low_balance(
                        balances['lighter'],
                        balances['paradex']
                    )
                except Exception as e:
                    print(f"⚠️  残高チェックエラー: {e}")

                # Open position
                open_result = await self.open_delta_neutral_position()

                if not open_result['success']:
                    print("⚠️  Failed to open position, retrying in 10 seconds...")
                    await asyncio.sleep(10)
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

        except asyncio.CancelledError:
            print("\n\n⚠️  Loop cancelled (async task cancelled)")
            await self.notifier.send_loop_stopped("Task cancelled")
            if self.position_open:
                print("🔄 Closing open position...")
                try:
                    await self.close_delta_neutral_position()
                except Exception as e:
                    print(f"❌ Error closing position: {e}")
                    print("⚠️  Manual intervention may be required")
            # Don't re-raise CancelledError - let cleanup happen gracefully
            return
        except KeyboardInterrupt:
            print("\n\n⚠️  Loop interrupted by user (Ctrl+C)")
            await self.notifier.send_loop_stopped("Interrupted by user")
            if self.position_open:
                print("🔄 Closing open position...")
                try:
                    await self.close_delta_neutral_position()
                except Exception as e:
                    print(f"❌ Error closing position: {e}")
                    print("⚠️  Manual intervention may be required")
            raise  # Re-raise KeyboardInterrupt to signal user interruption
        except Exception as e:
            print(f"\n❌ Error in loop: {e}")
            await self.notifier.send_error(f"Loop error: {e}", "Bot stopped due to error")
            if self.position_open:
                print("🔄 Attempting to close position...")
                await self.close_delta_neutral_position()
            raise
