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

    def __init__(self, private_key: str, account_index: int, api_key_index: int = 2, market: str = "DOGE", proxy_url: str = None):
        """
        Initialize Lighter client with official SDK

        Args:
            private_key: API key private key for signing transactions
            account_index: Account index from Lighter
            api_key_index: API key index (2-254, default 2)
            market: Trading market symbol
            proxy_url: Proxy URL with authentication (optional)
        """
        self.private_key = private_key
        self.account_index = account_index
        self.api_key_index = api_key_index
        self.market = market
        self.base_url = "https://mainnet.zklighter.elliot.ai"
        self.proxy_url = proxy_url

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
            # Try SDK first if available (currently not working, falls back to REST API)
            if self.client:
                try:
                    response = await self.client.api_client.call_api(
                        method='GET',
                        url='/markets'
                    )

                    if response and hasattr(response, 'data'):
                        import json
                        markets = json.loads(response.data) if isinstance(response.data, str) else response.data

                        if isinstance(markets, dict):
                            if 'markets' in markets:
                                markets = markets['markets']
                            elif 'data' in markets:
                                markets = markets['data']

                        if isinstance(markets, list):
                            for market in markets:
                                symbol = market.get('symbol', '') if isinstance(market, dict) else getattr(market, 'symbol', '')
                                if symbol.upper() == self.market.upper():
                                    if isinstance(market, dict):
                                        return float(market.get('last_price', 0) or market.get('mark_price', 0) or 0) or None
                                    else:
                                        return float(getattr(market, 'last_price', 0) or getattr(market, 'mark_price', 0) or 0) or None

                except Exception:
                    # SDK failed, fall back to REST API
                    pass

            # REST API fallback
            import aiohttp
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/api/v1/orderBookDetails?market={self.market}"

                try:
                    async with session.get(url, proxy=self.proxy_url) as response:
                        if response.status == 200:
                            data = await response.json()

                            # Extract price from orderBookDetails response
                            if isinstance(data, dict) and 'order_book_details' in data:
                                # Find DOGE market in order_book_details array
                                for book in data['order_book_details']:
                                    if book.get('symbol', '').upper() == self.market.upper():
                                        return float(book.get('last_trade_price', 0) or 0) or None

                            return None
                        else:
                            print(f"❌ Lighter API error: Status {response.status}")
                            return None

                except Exception as e:
                    print(f"❌ Lighter error: {e}")
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
                # Use REST API - public endpoint for account info
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    url = f"{self.base_url}/api/v1/account/{self.account_index}"
                    async with session.get(url) as response:
                        if response.status == 200:
                            return await response.json()
                        else:
                            print(f"ℹ️  Lighter account balance unavailable (SDK required for private data)")
                            return {"status": "SDK_REQUIRED", "message": "Install Lighter SDK for full account access"}

        except Exception as e:
            print(f"ℹ️  Lighter balance info unavailable: {e}")
            return {"status": "UNAVAILABLE"}

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
