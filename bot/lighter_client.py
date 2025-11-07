"""
Lighter DEX client implementation
Handles connection and trading operations on Lighter
"""

import asyncio
from typing import Dict, Any, Optional

# Try to import SDK, but make it optional
try:
    from lighter.client import LighterClient as LighterSDK
    LIGHTER_SDK_AVAILABLE = True
except ImportError:
    try:
        # Try alternative import path
        from lighter_sdk import LighterClient as LighterSDK
        LIGHTER_SDK_AVAILABLE = True
    except ImportError:
        LighterSDK = None
        LIGHTER_SDK_AVAILABLE = False
        print("⚠ Lighter SDK not available, using REST API")


class LighterClient:
    """Client for interacting with Lighter DEX"""

    def __init__(self, api_key: str, api_secret: str, private_key: str, market: str = "XMR"):
        """
        Initialize Lighter client

        Args:
            api_key: Lighter API key
            api_secret: Lighter API secret
            private_key: Private key for signing transactions
            market: Trading market symbol
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.private_key = private_key
        self.market = market

        # Initialize Lighter SDK
        # Note: This initialization may need to be adjusted based on actual SDK
        if LighterSDK:
            self.client = LighterSDK(
                api_key=api_key,
                api_secret=api_secret,
                private_key=private_key
            )
            print(f"✓ Lighter initialized with SDK")
        else:
            self.client = None
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
                # Using SDK
                orderbook = await self._get_orderbook_sdk()
            else:
                # Using REST API
                orderbook = await self._get_orderbook_rest()

            if not orderbook:
                return None

            # Calculate mid price from best bid/ask
            bids = orderbook.get('bids', [])
            asks = orderbook.get('asks', [])

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

    async def _get_orderbook_sdk(self) -> Optional[Dict[str, Any]]:
        """Get orderbook using SDK"""
        try:
            return self.client.get_orderbook(self.market)
        except Exception as e:
            print(f"❌ Lighter SDK orderbook error: {e}")
            return None

    async def _get_orderbook_rest(self) -> Optional[Dict[str, Any]]:
        """Get orderbook using REST API"""
        import aiohttp

        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://api.lighter.xyz/v1/orderbook/{self.market}"
                headers = {
                    'X-API-KEY': self.api_key
                }

                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        print(f"❌ Lighter API error: {response.status}")
                        return None

        except Exception as e:
            print(f"❌ Lighter REST API error: {e}")
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
            if self.client:
                # Using SDK
                result = await self._place_order_sdk(side, size)
            else:
                # Using REST API
                result = await self._place_order_rest(side, size)

            if result:
                print(f"✓ Lighter order placed: {side} {size} {self.market}")
                print(f"  Order ID: {result.get('id', 'N/A')}")

            return result

        except Exception as e:
            print(f"❌ Lighter order error: {e}")
            return None

    async def _place_order_sdk(self, side: str, size: float) -> Optional[Dict[str, Any]]:
        """Place order using SDK"""
        try:
            return self.client.place_market_order(
                ticker=self.market,
                side=side.upper(),
                amount=size
            )
        except Exception as e:
            print(f"❌ Lighter SDK order error: {e}")
            return None

    async def _place_order_rest(self, side: str, size: float) -> Optional[Dict[str, Any]]:
        """Place order using REST API"""
        import aiohttp
        import time
        import hmac
        import hashlib

        try:
            async with aiohttp.ClientSession() as session:
                url = "https://api.lighter.xyz/v1/orders"

                # Prepare order data
                timestamp = str(int(time.time() * 1000))
                order_data = {
                    'ticker': self.market,
                    'side': side.upper(),
                    'type': 'MARKET',
                    'amount': str(size),
                    'timestamp': timestamp
                }

                # Create signature
                message = '&'.join([f"{k}={v}" for k, v in sorted(order_data.items())])
                signature = hmac.new(
                    self.api_secret.encode(),
                    message.encode(),
                    hashlib.sha256
                ).hexdigest()

                headers = {
                    'X-API-KEY': self.api_key,
                    'X-SIGNATURE': signature,
                    'Content-Type': 'application/json'
                }

                async with session.post(url, json=order_data, headers=headers) as response:
                    if response.status in [200, 201]:
                        return await response.json()
                    else:
                        error_text = await response.text()
                        print(f"❌ Lighter API error: {response.status} - {error_text}")
                        return None

        except Exception as e:
            print(f"❌ Lighter REST API error: {e}")
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
            if self.client:
                return self.client.get_order(order_id)
            else:
                # REST API implementation
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    url = f"https://api.lighter.xyz/v1/orders/{order_id}"
                    headers = {'X-API-KEY': self.api_key}

                    async with session.get(url, headers=headers) as response:
                        if response.status == 200:
                            return await response.json()
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
                return self.client.get_account()
            else:
                # REST API implementation
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    url = "https://api.lighter.xyz/v1/account"
                    headers = {'X-API-KEY': self.api_key}

                    async with session.get(url, headers=headers) as response:
                        if response.status == 200:
                            return await response.json()
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
            if self.client:
                self.client.cancel_order(order_id)
            else:
                # REST API implementation
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    url = f"https://api.lighter.xyz/v1/orders/{order_id}"
                    headers = {'X-API-KEY': self.api_key}

                    async with session.delete(url, headers=headers) as response:
                        if response.status not in [200, 204]:
                            return False

            print(f"✓ Lighter order cancelled: {order_id}")
            return True

        except Exception as e:
            print(f"❌ Lighter cancel error: {e}")
            return False
