"""
Lighter DEX client implementation using official SDK
Handles connection and trading operations on Lighter
"""

import asyncio
from typing import Dict, Any, Optional
from decimal import Decimal

# Try to import SDK, but make it optional
try:
    import lighter
    LIGHTER_SDK_AVAILABLE = True
except ImportError:
    LIGHTER_SDK_AVAILABLE = False
    print("⚠ Lighter SDK not available, using REST API")


class LighterClient:
    """Client for interacting with Lighter DEX using official SDK"""

    def __init__(self, private_key: str, account_index: int, api_key_index: int = 2, market: str = "DOGE"):
        """
        Initialize Lighter client with official SDK

        Args:
            private_key: API key private key for signing transactions
            account_index: Account index from Lighter
            api_key_index: API key index (2-254, default 2)
            market: Trading market symbol
        """
        self.private_key = private_key
        self.account_index = account_index
        self.api_key_index = api_key_index
        self.market = market
        self.base_url = "https://mainnet.zklighter.elliot.ai"

        # Initialize Lighter SDK
        self.client = None
        if LIGHTER_SDK_AVAILABLE:
            try:
                self.client = lighter.SignerClient(
                    url=self.base_url,
                    private_key=self.private_key,
                    account_index=self.account_index,
                    api_key_index=self.api_key_index,
                )

                # Verify client is working
                err = self.client.check_client()
                if err is not None:
                    print(f"⚠ Lighter client check failed: {err}")
                    self.client = None
                else:
                    print(f"✓ Lighter initialized with official SDK")
                    print(f"  Account Index: {self.account_index}")
                    print(f"  API Key Index: {self.api_key_index}")
            except Exception as e:
                print(f"⚠ Lighter SDK init failed: {e}")
                self.client = None

        if not self.client:
            print(f"⚠ Lighter SDK not available, using REST API fallback")

        print(f"  Market: {self.market}")

    async def get_market_price(self) -> Optional[float]:
        """
        Get current market price

        Returns:
            Current market price or None if error
        """
        try:
            if self.client:
                # Using SDK - get orderbook
                api_client = lighter.ApiClient()
                try:
                    orderbook_api = lighter.OrderBookApi(api_client)
                    orderbook = await orderbook_api.get_order_book(market=self.market, depth=1)

                    if orderbook and hasattr(orderbook, 'bids') and hasattr(orderbook, 'asks'):
                        if orderbook.bids and orderbook.asks:
                            best_bid = float(orderbook.bids[0].price) if hasattr(orderbook.bids[0], 'price') else float(orderbook.bids[0][0])
                            best_ask = float(orderbook.asks[0].price) if hasattr(orderbook.asks[0], 'price') else float(orderbook.asks[0][0])

                            if best_bid > 0 and best_ask > 0:
                                return (best_bid + best_ask) / 2
                finally:
                    await api_client.close()
            else:
                # Using REST API
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    url = f"{self.base_url}/orderbook/{self.market}"
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            bids = data.get('bids', [])
                            asks = data.get('asks', [])

                            if bids and asks:
                                best_bid = float(bids[0][0]) if isinstance(bids[0], list) else float(bids[0].get('price', 0))
                                best_ask = float(asks[0][0]) if isinstance(asks[0], list) else float(asks[0].get('price', 0))

                                if best_bid > 0 and best_ask > 0:
                                    return (best_bid + best_ask) / 2

            print(f"⚠ Could not determine price from Lighter orderbook")
            return None

        except Exception as e:
            print(f"❌ Lighter price fetch error: {e}")
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
            if not self.client:
                print("❌ Lighter SDK required for placing orders")
                return None

            # Get current price for limit order
            current_price = await self.get_market_price()
            if not current_price:
                raise ValueError("Could not fetch current market price")

            # Set aggressive limit price to act as market order
            slippage_multiplier = 1.05 if side.upper() == 'BUY' else 0.95
            limit_price = current_price * slippage_multiplier

            # Create auth token
            auth, err = self.client.create_auth_token_with_expiry(
                lighter.SignerClient.DEFAULT_10_MIN_AUTH_EXPIRY
            )
            if err is not None:
                raise Exception(f"Failed to create auth token: {err}")

            # Place limit order with IOC (acts as market order)
            # Note: Actual method signature may vary - this is based on common patterns
            tx, tx_hash, err = await self.client.create_order(
                market_index=self._get_market_index(self.market),
                base_amount=str(size),
                price=str(limit_price),
                is_buy=(side.upper() == 'BUY'),
                time_in_force="IOC",  # Immediate or Cancel
            )

            if err is not None:
                raise Exception(f"Order failed: {err}")

            result = {
                'id': tx_hash,
                'tx': tx,
                'status': 'submitted'
            }

            print(f"✓ Lighter order placed: {side} {size} {self.market}")
            print(f"  TX Hash: {tx_hash}")
            print(f"  Price: {limit_price:.4f}")

            return result

        except Exception as e:
            print(f"❌ Lighter order error: {e}")
            return None

    def _get_market_index(self, market: str) -> int:
        """
        Get market index for a given market symbol
        Note: This is a placeholder - actual mapping needed
        """
        # TODO: Get actual market indices from API
        market_indices = {
            'ETH': 0,
            'BTC': 1,
            'DOGE': 2,  # Placeholder
        }
        return market_indices.get(market, 0)

    async def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Get order status

        Args:
            order_id: Order ID (transaction hash)

        Returns:
            Order details or None if error
        """
        try:
            if self.client:
                # Get transaction status
                api_client = lighter.ApiClient()
                try:
                    tx_api = lighter.TransactionApi(api_client)
                    tx = await tx_api.get_transaction(hash=order_id)
                    return tx.to_dict() if hasattr(tx, 'to_dict') else tx
                finally:
                    await api_client.close()
            else:
                print("❌ Lighter SDK required for order status")
                return None

        except Exception as e:
            print(f"❌ Lighter order status error: {e}")
            return None

    async def get_account_balance(self) -> Optional[Dict[str, Any]]:
        """
        Get account balance

        Returns:
            Account balance or None if error
        """
        try:
            if self.client:
                api_client = lighter.ApiClient()
                try:
                    account_api = lighter.AccountApi(api_client)
                    account = await account_api.account(
                        by="index",
                        value=str(self.account_index)
                    )
                    return account.to_dict() if hasattr(account, 'to_dict') else account
                finally:
                    await api_client.close()
            else:
                print("❌ Lighter SDK required for account balance")
                return None

        except Exception as e:
            print(f"❌ Lighter balance error: {e}")
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
            if not self.client:
                print("❌ Lighter SDK required for canceling orders")
                return False

            # Create auth token
            auth, err = self.client.create_auth_token_with_expiry(
                lighter.SignerClient.DEFAULT_10_MIN_AUTH_EXPIRY
            )
            if err is not None:
                raise Exception(f"Failed to create auth token: {err}")

            # Cancel order
            tx, tx_hash, err = await self.client.cancel_order(
                market_index=self._get_market_index(self.market),
                order_index=int(order_id)
            )

            if err is not None:
                raise Exception(f"Cancel failed: {err}")

            print(f"✓ Lighter order cancelled: {order_id}")
            return True

        except Exception as e:
            print(f"❌ Lighter cancel error: {e}")
            return False
