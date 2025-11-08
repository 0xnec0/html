"""
Main trading bot for simultaneous execution across Paradex and Lighter
"""

import asyncio
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime

from .paradex_client import ParadexClient
from .lighter_client import LighterClient
from .config import Config


class TradingBot:
    """Trading bot for simultaneous execution on multiple DEX platforms"""

    def __init__(self, config: Config):
        """
        Initialize trading bot

        Args:
            config: Configuration object
        """
        self.config = config

        # Initialize clients
        self.paradex = ParadexClient(
            env=config.paradex_env,
            l1_address=config.paradex_l1_address,
            l1_private_key=config.paradex_l1_private_key,
            market=config.paradex_market,
            l2_address=config.paradex_l2_address,
            l2_private_key=config.paradex_l2_private_key
        )

        self.lighter = LighterClient(
            private_key=config.lighter_private_key,
            account_index=config.lighter_account_index,
            api_key_index=config.lighter_api_key_index,
            market=config.lighter_market
        )

        print("\n✓ Trading bot initialized")

    async def get_prices(self) -> Tuple[Optional[float], Optional[float]]:
        """
        Get current prices from both exchanges

        Returns:
            Tuple of (paradex_price, lighter_price)
        """
        print("\n📊 Fetching prices...")

        # Fetch prices concurrently
        paradex_price_task = self.paradex.get_market_price()
        lighter_price_task = self.lighter.get_market_price()

        paradex_price, lighter_price = await asyncio.gather(
            paradex_price_task,
            lighter_price_task,
            return_exceptions=True
        )

        # Handle exceptions
        if isinstance(paradex_price, Exception):
            print(f"❌ Paradex price error: {paradex_price}")
            paradex_price = None

        if isinstance(lighter_price, Exception):
            print(f"❌ Lighter price error: {lighter_price}")
            lighter_price = None

        # Display prices
        if paradex_price:
            print(f"  Paradex: ${paradex_price:.2f}")
        if lighter_price:
            print(f"  Lighter: ${lighter_price:.2f}")

        if paradex_price and lighter_price:
            spread = abs(paradex_price - lighter_price)
            spread_pct = (spread / min(paradex_price, lighter_price)) * 100
            print(f"  Spread: ${spread:.2f} ({spread_pct:.2f}%)")

        return paradex_price, lighter_price

    async def execute_simultaneous_trade(
        self,
        side: str,
        amount: float,
        paradex_only: bool = False,
        lighter_only: bool = False
    ) -> Dict[str, Any]:
        """
        Execute simultaneous trades on both exchanges

        Args:
            side: Order side ('BUY' or 'SELL')
            amount: Amount to trade
            paradex_only: Only trade on Paradex
            lighter_only: Only trade on Lighter

        Returns:
            Dictionary with execution results
        """
        timestamp = datetime.now().isoformat()
        print(f"\n🚀 Executing {side} order for {amount} XMR")
        print(f"   Timestamp: {timestamp}")

        results = {
            'timestamp': timestamp,
            'side': side,
            'amount': amount,
            'paradex': None,
            'lighter': None,
            'success': False
        }

        # Create order tasks
        tasks = []
        task_names = []

        if not lighter_only:
            tasks.append(self.paradex.place_market_order(side, amount))
            task_names.append('paradex')

        if not paradex_only:
            tasks.append(self.lighter.place_market_order(side, amount))
            task_names.append('lighter')

        # Execute orders concurrently for simultaneous execution
        print("\n⏱️  Executing orders simultaneously...")
        start_time = asyncio.get_event_loop().time()

        order_results = await asyncio.gather(*tasks, return_exceptions=True)

        execution_time = asyncio.get_event_loop().time() - start_time
        print(f"⏱️  Total execution time: {execution_time:.3f}s")

        # Process results
        for i, (task_name, result) in enumerate(zip(task_names, order_results)):
            if isinstance(result, Exception):
                print(f"❌ {task_name.capitalize()} order failed: {result}")
                results[task_name] = {'error': str(result)}
            else:
                results[task_name] = result

        # Determine overall success
        paradex_success = results['paradex'] is not None and 'error' not in results.get('paradex', {})
        lighter_success = results['lighter'] is not None and 'error' not in results.get('lighter', {})

        if paradex_only:
            results['success'] = paradex_success
        elif lighter_only:
            results['success'] = lighter_success
        else:
            results['success'] = paradex_success and lighter_success

        # Summary
        print("\n" + "="*60)
        if results['success']:
            print("✅ All orders executed successfully!")
        else:
            print("⚠️  Some orders failed")

        print(f"   Paradex: {'✓' if paradex_success else '✗'}")
        print(f"   Lighter: {'✓' if lighter_success else '✗'}")
        print("="*60)

        return results

    async def monitor_positions(self) -> Dict[str, Any]:
        """
        Monitor current positions and balances

        Returns:
            Dictionary with position information
        """
        print("\n📈 Fetching positions...")

        # Fetch balances concurrently
        paradex_balance_task = self.paradex.get_account_balance()
        lighter_balance_task = self.lighter.get_account_balance()

        paradex_balance, lighter_balance = await asyncio.gather(
            paradex_balance_task,
            lighter_balance_task,
            return_exceptions=True
        )

        results = {
            'paradex': paradex_balance if not isinstance(paradex_balance, Exception) else None,
            'lighter': lighter_balance if not isinstance(lighter_balance, Exception) else None
        }

        # Display results
        if results['paradex']:
            print(f"  Paradex: {results['paradex']}")
        if results['lighter']:
            print(f"  Lighter: {results['lighter']}")

        return results

    async def check_arbitrage_opportunity(self, min_spread_pct: float = 0.5) -> Optional[Dict[str, Any]]:
        """
        Check for arbitrage opportunities

        Args:
            min_spread_pct: Minimum spread percentage to consider

        Returns:
            Arbitrage opportunity details or None
        """
        print(f"\n🔍 Checking for arbitrage opportunities (min spread: {min_spread_pct}%)...")

        paradex_price, lighter_price = await self.get_prices()

        if not paradex_price or not lighter_price:
            print("⚠️  Could not fetch prices from both exchanges")
            return None

        spread = abs(paradex_price - lighter_price)
        spread_pct = (spread / min(paradex_price, lighter_price)) * 100

        if spread_pct < min_spread_pct:
            print(f"ℹ️  No arbitrage opportunity (spread: {spread_pct:.2f}%)")
            return None

        # Determine buy/sell sides
        if paradex_price < lighter_price:
            buy_exchange = 'paradex'
            sell_exchange = 'lighter'
            profit_pct = ((lighter_price - paradex_price) / paradex_price) * 100
        else:
            buy_exchange = 'lighter'
            sell_exchange = 'paradex'
            profit_pct = ((paradex_price - lighter_price) / lighter_price) * 100

        opportunity = {
            'buy_exchange': buy_exchange,
            'sell_exchange': sell_exchange,
            'buy_price': min(paradex_price, lighter_price),
            'sell_price': max(paradex_price, lighter_price),
            'spread': spread,
            'spread_pct': spread_pct,
            'profit_pct': profit_pct,
            'timestamp': datetime.now().isoformat()
        }

        print("\n💡 Arbitrage opportunity found!")
        print(f"   Buy on {buy_exchange.capitalize()}: ${opportunity['buy_price']:.2f}")
        print(f"   Sell on {sell_exchange.capitalize()}: ${opportunity['sell_price']:.2f}")
        print(f"   Potential profit: {profit_pct:.2f}%")

        return opportunity

    async def execute_arbitrage(self, amount: float) -> Dict[str, Any]:
        """
        Execute arbitrage trade

        Args:
            amount: Amount to trade

        Returns:
            Execution results
        """
        opportunity = await self.check_arbitrage_opportunity()

        if not opportunity:
            return {'success': False, 'error': 'No arbitrage opportunity'}

        print(f"\n💰 Executing arbitrage for {amount} XMR...")

        # Execute simultaneous buy and sell
        tasks = []
        task_names = []

        if opportunity['buy_exchange'] == 'paradex':
            tasks.append(self.paradex.place_market_order('BUY', amount))
            tasks.append(self.lighter.place_market_order('SELL', amount))
        else:
            tasks.append(self.lighter.place_market_order('BUY', amount))
            tasks.append(self.paradex.place_market_order('SELL', amount))

        task_names = ['buy_order', 'sell_order']

        # Execute
        results = await asyncio.gather(*tasks, return_exceptions=True)

        execution_result = {
            'opportunity': opportunity,
            'buy_order': results[0] if not isinstance(results[0], Exception) else {'error': str(results[0])},
            'sell_order': results[1] if not isinstance(results[1], Exception) else {'error': str(results[1])},
            'success': all(not isinstance(r, Exception) for r in results)
        }

        if execution_result['success']:
            print("\n✅ Arbitrage executed successfully!")
        else:
            print("\n❌ Arbitrage execution failed")

        return execution_result

    async def test_connections(self) -> Dict[str, Any]:
        """
        Test connections to both exchanges

        Returns:
            Dictionary with connection test results
        """
        print("\n🔌 Testing connections to exchanges...")
        print("="*60)

        results = {
            'paradex': {'connected': False, 'details': None, 'error': None},
            'lighter': {'connected': False, 'details': None, 'error': None}
        }

        # Test Paradex connection
        print("\n📍 Testing Paradex connection...")
        try:
            # Try to fetch account balance as connection test
            account_data = await self.paradex.get_account_balance()

            if account_data:
                results['paradex']['connected'] = True
                results['paradex']['details'] = account_data
                print("  ✅ Paradex: Connected successfully")

                # Display account info
                if isinstance(account_data, dict):
                    if 'account' in account_data:
                        acc = account_data['account']
                        print(f"     Account ID: {acc.get('account_id', 'N/A')}")
                        print(f"     Status: {acc.get('status', 'N/A')}")

                    # Show balances if available
                    if 'balances' in account_data:
                        balances = account_data['balances']
                        if balances:
                            print(f"     Balances: {len(balances)} asset(s)")
                            for bal in balances[:3]:  # Show first 3
                                asset = bal.get('asset', 'Unknown')
                                amount = bal.get('available', '0')
                                print(f"       - {asset}: {amount}")
            else:
                results['paradex']['error'] = "No data returned"
                print("  ⚠️  Paradex: Connection unclear (no data returned)")

        except Exception as e:
            results['paradex']['error'] = str(e)
            print(f"  ❌ Paradex: Connection failed - {e}")

        # Test Lighter connection
        print("\n📍 Testing Lighter connection...")
        try:
            # Try to fetch account balance as connection test
            account_data = await self.lighter.get_account_balance()

            if account_data:
                results['lighter']['connected'] = True
                results['lighter']['details'] = account_data
                print("  ✅ Lighter: Connected successfully")

                # Display account info
                if isinstance(account_data, dict):
                    if 'account' in account_data:
                        print(f"     Account: {account_data['account']}")
                    if 'balances' in account_data:
                        balances = account_data['balances']
                        if balances:
                            print(f"     Balances: {len(balances)} asset(s)")
            else:
                results['lighter']['error'] = "No data returned"
                print("  ⚠️  Lighter: Connection unclear (no data returned)")

        except Exception as e:
            results['lighter']['error'] = str(e)
            print(f"  ❌ Lighter: Connection failed - {e}")

        # Summary
        print("\n" + "="*60)
        print("📊 CONNECTION TEST SUMMARY")
        print("="*60)

        paradex_status = "✅ Connected" if results['paradex']['connected'] else "❌ Failed"
        lighter_status = "✅ Connected" if results['lighter']['connected'] else "❌ Failed"

        print(f"  Paradex: {paradex_status}")
        print(f"  Lighter: {lighter_status}")

        all_connected = results['paradex']['connected'] and results['lighter']['connected']

        if all_connected:
            print("\n🎉 All exchanges connected successfully!")
        elif results['paradex']['connected'] or results['lighter']['connected']:
            print("\n⚠️  Some exchanges failed to connect")
        else:
            print("\n❌ All connections failed")

        print("="*60)

        return results
