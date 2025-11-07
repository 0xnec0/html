"""
Paradex DEX client implementation
Handles connection and trading operations on Paradex
"""

import asyncio
from typing import Dict, Any, Optional
from paradex_py import Paradex
from paradex_py.environment import Environment


class ParadexClient:
    """Client for interacting with Paradex DEX"""

    def __init__(self, env: str, l1_address: str, l1_private_key: str, market: str = "XMR-USD-PERP"):
        """
        Initialize Paradex client

        Args:
            env: Environment (TESTNET or MAINNET)
            l1_address: Ethereum L1 address
            l1_private_key: Ethereum L1 private key
            market: Trading market symbol
        """
        self.market = market
        self.env = Environment.TESTNET if env.upper() == "TESTNET" else Environment.PROD

        # Initialize Paradex SDK
        self.client = Paradex(
            env=self.env,
            l1_address=l1_address,
            l1_private_key=l1_private_key
        )

        print(f"✓ Paradex initialized")
        print(f"  L2 Address: {hex(self.client.account.l2_address)}")
        print(f"  Market: {self.market}")

    async def get_market_price(self) -> Optional[float]:
        """
        Get current market price

        Returns:
            Current market price or None if error
        """
        try:
            # Fetch market summary
            summary = self.client.api_client.fetch_markets_summary()

            # Find XMR market
            for market_data in summary.get('results', []):
                if market_data.get('market') == self.market:
                    # Get mid price from best bid/ask
                    best_bid = float(market_data.get('best_bid', 0))
                    best_ask = float(market_data.get('best_ask', 0))
                    if best_bid > 0 and best_ask > 0:
                        return (best_bid + best_ask) / 2
                    return float(market_data.get('last_price', 0))

            print(f"⚠ Market {self.market} not found in Paradex")
            return None

        except Exception as e:
            print(f"❌ Paradex price fetch error: {e}")
            return None

    async def place_market_order(self, side: str, size: float) -> Optional[Dict[str, Any]]:
        """
        Place a market order

        Args:
            side: Order side ('BUY' or 'SELL')
            size: Order size

        Returns:
            Order result or None if error
        """
        try:
            # Get current market price for limit price calculation
            current_price = await self.get_market_price()
            if not current_price:
                raise ValueError("Could not fetch current market price")

            # Set aggressive limit price to ensure fill
            # For buy orders, use price slightly above market
            # For sell orders, use price slightly below market
            slippage_multiplier = 1.01 if side.upper() == 'BUY' else 0.99
            limit_price = current_price * slippage_multiplier

            # Place limit order that acts as market order
            order_params = {
                'market': self.market,
                'side': side.upper(),
                'type': 'LIMIT',
                'size': str(size),
                'limit_price': str(limit_price),
                'time_in_force': 'IOC',  # Immediate or Cancel
            }

            result = self.client.api_client.create_order(**order_params)

            print(f"✓ Paradex order placed: {side} {size} {self.market}")
            print(f"  Order ID: {result.get('id', 'N/A')}")
            print(f"  Price: {limit_price:.2f}")

            return result

        except Exception as e:
            print(f"❌ Paradex order error: {e}")
            return None

    async def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Get order status

        Args:
            order_id: Order ID

        Returns:
            Order details or None if error
        """
        try:
            order = self.client.api_client.fetch_order(order_id)
            return order
        except Exception as e:
            print(f"❌ Paradex order status error: {e}")
            return None

    async def get_account_balance(self) -> Optional[Dict[str, Any]]:
        """
        Get account balance

        Returns:
            Account balance or None if error
        """
        try:
            account = self.client.api_client.fetch_account()
            return account
        except Exception as e:
            print(f"❌ Paradex balance error: {e}")
            return None

    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order

        Args:
            order_id: Order ID

        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.api_client.cancel_order(order_id)
            print(f"✓ Paradex order cancelled: {order_id}")
            return True
        except Exception as e:
            print(f"❌ Paradex cancel error: {e}")
            return False
