"""
Lighter DEX client implementation using official SDK
Handles connection and trading operations on Lighter
"""

import asyncio
import time
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

        # Cache for market ID and decimal info lookup
        self._market_id_cache = {}
        self._market_info_cache = {}  # Store full market details including decimals

        # HTTP session for REST API calls (will be created on first use)
        self._session = None

    async def _get_session(self):
        """Get or create aiohttp session"""
        if self._session is None or self._session.closed:
            import aiohttp
            self._session = aiohttp.ClientSession()
        return self._session

    async def _get_market_id_from_api(self, symbol: str) -> Optional[int]:
        """
        Get market_id from Lighter API for given symbol

        Args:
            symbol: Market symbol (e.g., 'JUP', 'DOGE')

        Returns:
            market_id or None if not found
        """
        # Check cache first
        if symbol in self._market_id_cache:
            return self._market_id_cache[symbol]

        try:
            session = await self._get_session()
            url = f"{self.base_url}/api/v1/orderBookDetails?market={symbol}"
            async with session.get(url, proxy=self.proxy_url) as response:
                if response.status == 200:
                    data = await response.json()
                    if isinstance(data, dict) and 'order_book_details' in data:
                        for book in data['order_book_details']:
                            if book.get('symbol', '').upper() == symbol.upper():
                                market_id = book.get('market_id')
                                if market_id is not None:
                                    # Cache market_id and full details
                                    self._market_id_cache[symbol] = market_id
                                    self._market_info_cache[symbol] = book

                                    # Show decimal info
                                    price_decimals = book.get('price_decimals', 0)
                                    size_decimals = book.get('size_decimals', 0)
                                    print(f"ℹ️  Found market_id for {symbol}: {market_id}")
                                    print(f"   Price decimals: {price_decimals}, Size decimals: {size_decimals}")

                                    return market_id
        except Exception as e:
            print(f"⚠ Failed to fetch market_id for {symbol}: {e}")

        return None

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
            session = await self._get_session()
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

    async def get_bid_ask(self) -> Optional[tuple]:
        """
        Get current bid and ask prices

        Returns:
            Tuple of (bid, ask) or None if error
        """
        try:
            import aiohttp
            session = await self._get_session()
            url = f"{self.base_url}/api/v1/orderBookDetails?market={self.market}"

            try:
                async with session.get(url, proxy=self.proxy_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()

                        # Extract bid/ask from orderBookDetails response
                        if isinstance(data, dict) and 'order_book_details' in data:
                            for book in data['order_book_details']:
                                symbol = book.get('symbol', '')

                                if symbol.upper() == self.market.upper():
                                    # Get best bid (highest buy price) and best ask (lowest sell price)
                                    asks = book.get('asks', [])
                                    bids = book.get('bids', [])

                                    if asks and bids and len(asks) > 0 and len(bids) > 0:
                                        # asks[0] = [price, size]
                                        # bids[0] = [price, size]
                                        best_ask = float(asks[0][0])
                                        best_bid = float(bids[0][0])

                                        if best_bid > 0 and best_ask > 0:
                                            return (best_bid, best_ask)
                                    else:
                                        # Orderbook is empty, use last_trade_price as fallback
                                        last_price = book.get('last_trade_price', 0)
                                        if last_price and float(last_price) > 0:
                                            last_price = float(last_price)
                                            # Estimate bid/ask with small spread (0.01%)
                                            spread = last_price * 0.0001
                                            estimated_bid = last_price - spread / 2
                                            estimated_ask = last_price + spread / 2
                                            print(f"⚠️  {symbol}: オーダーブック空 - 最終取引価格を使用 (${last_price:.4f})")
                                            return (estimated_bid, estimated_ask)
                                        else:
                                            print(f"❌ {symbol}: オーダーブックと最終取引価格がありません")

                            print(f"❌ Market '{self.market}' not found!")
                        else:
                            print(f"❌ Invalid response structure")
                        return None
                    else:
                        print(f"❌ HTTP {response.status}")
                        return None

            except asyncio.TimeoutError:
                print(f"❌ Timeout")
                return None
            except aiohttp.ClientError as e:
                print(f"❌ ClientError: {e}")
                return None

        except Exception:
            return None

    async def place_limit_order(self, side: str, size: float, price: float) -> Optional[Dict[str, Any]]:
        """
        Place a limit order

        Args:
            side: Order side ('BUY' or 'SELL')
            size: Order size
            price: Limit price

        Returns:
            Order result with order_id or None if error
        """
        try:
            if not self.client:
                print("❌ Lighter SDK required for placing orders")
                return None

            # Create auth token
            auth, err = self.client.create_auth_token_with_expiry(
                lighter.SignerClient.DEFAULT_10_MIN_AUTH_EXPIRY
            )
            if err is not None:
                raise Exception(f"Failed to create auth token: {err}")

            # Generate unique client order index (timestamp in milliseconds)
            client_order_index = int(time.time() * 1000)

            # Get market_id from API
            market_id = await self._get_market_id_from_api(self.market)
            if market_id is None:
                raise ValueError(f"Could not find market_id for {self.market}")

            # Get market info for decimal conversion
            market_info = self._market_info_cache.get(self.market)
            if not market_info:
                raise ValueError(f"Market info not found for {self.market}")

            # Extract decimal precision
            price_decimals = market_info.get('price_decimals', 0)
            size_decimals = market_info.get('size_decimals', 0)

            # Convert to integers using decimal precision
            price_int = int(price * (10 ** price_decimals))
            base_amount_int = int(size * (10 ** size_decimals))

            # Place limit order using create_market_order with tight price
            # Note: Lighter's create_market_order with avg_execution_price acts like a limit order
            # avg_execution_price is the maximum price we're willing to accept
            tx, tx_hash, err = await self.client.create_market_order(
                market_index=market_id,
                base_amount=base_amount_int,  # Integer
                avg_execution_price=price_int,  # Integer - limit price (max acceptable)
                is_ask=(side.upper() == 'SELL'),  # True for SELL, False for BUY
                client_order_index=client_order_index,
                reduce_only=False,
            )

            if err is not None:
                raise Exception(f"Order failed: {err}")

            result = {
                'order_id': client_order_index,  # Use client order index as order ID
                'tx_hash': tx_hash,
                'tx': tx,
                'status': 'submitted',
                'side': side,
                'size': size,
                'price': price
            }

            print(f"✓ Lighter limit order placed: {side} {size} @ ${price:.4f}")
            print(f"  Order ID: {client_order_index}")
            print(f"  TX Hash: {tx_hash}")

            return result

        except Exception as e:
            print(f"❌ Lighter limit order error: {e}")
            return None

    async def get_order_status(self, order_id: int) -> Optional[str]:
        """
        Get order status by order ID

        Args:
            order_id: Client order index used when placing the order

        Returns:
            Order status: 'FILLED', 'PENDING', 'CANCELLED', 'FAILED', or None if error
        """
        try:
            if not self.client:
                print("❌ Lighter SDK required for checking order status")
                return None

            # Get market_id
            market_id = await self._get_market_id_from_api(self.market)
            if market_id is None:
                return None

            # Query order status from Lighter API
            # Note: Lighter SDK might not have direct order status query
            # We may need to use REST API to check order status

            # For now, assume order is filled after a short delay
            # This is a placeholder - actual implementation depends on Lighter API
            # TODO: Implement actual order status check via Lighter API/SDK

            print(f"ℹ️  Checking order status for order {order_id}...")
            return 'PENDING'  # Placeholder

        except Exception as e:
            print(f"❌ Error checking order status: {e}")
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

            # Generate unique client order index (timestamp in milliseconds)
            client_order_index = int(time.time() * 1000)

            # Get market_id from API
            market_id = await self._get_market_id_from_api(self.market)
            if market_id is None:
                raise ValueError(f"Could not find market_id for {self.market}")

            # Get market info for decimal conversion
            market_info = self._market_info_cache.get(self.market)
            if not market_info:
                raise ValueError(f"Market info not found for {self.market}")

            # Extract decimal precision
            price_decimals = market_info.get('price_decimals', 0)
            size_decimals = market_info.get('size_decimals', 0)

            # Convert to integers using decimal precision
            # Lighter SDK requires integers (fixed-point representation)
            price_int = int(limit_price * (10 ** price_decimals))
            base_amount_int = int(size * (10 ** size_decimals))

            print(f"ℹ️  Converting to integers:")
            print(f"   Price: {limit_price} → {price_int} (decimals: {price_decimals})")
            print(f"   Size: {size} → {base_amount_int} (decimals: {size_decimals})")

            # Place market order using create_market_order
            tx, tx_hash, err = await self.client.create_market_order(
                market_index=market_id,
                base_amount=base_amount_int,  # Integer
                avg_execution_price=price_int,  # Integer - max acceptable price
                is_ask=(side.upper() == 'SELL'),  # True for SELL, False for BUY
                client_order_index=client_order_index,
                reduce_only=False,  # Not reducing existing position
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
        Note: These indices need to be verified with Lighter API
        """
        # Market indices from Lighter protocol
        # These should be verified via /api/v1/orderBookDetails
        market_indices = {
            'ETH': 0,
            'BTC': 1,
            'DOGE': 2,
            'JUP': 3,  # Jupiter - verify actual index
            'SOL': 4,
        }
        index = market_indices.get(market.upper(), None)
        if index is None:
            print(f"⚠ Unknown market {market}, defaulting to index 0")
            return 0
        return index

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
                session = await self._get_session()
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

    async def get_funding_rate(self) -> Optional[float]:
        """
        Get current funding rate for the market

        Returns:
            Current funding rate (8-hour rate) or None if error
            Positive = longs pay shorts, Negative = shorts pay longs
        """
        try:
            session = await self._get_session()

            # Try to get funding rate from orderBookDetails
            url = f"{self.base_url}/api/v1/orderBookDetails?market={self.market}"
            async with session.get(url, proxy=self.proxy_url) as response:
                if response.status == 200:
                    data = await response.json()

                    if isinstance(data, dict) and 'order_book_details' in data:
                        for book in data['order_book_details']:
                            if book.get('symbol', '').upper() == self.market.upper():
                                # funding_rate_8h is the 8-hour funding rate
                                funding_rate = book.get('funding_rate_8h') or book.get('funding_rate')
                                if funding_rate is not None:
                                    return float(funding_rate)

                    print(f"⚠️  Funding rate not found for {self.market}")
                    return None
                else:
                    print(f"⚠️  Failed to fetch Lighter funding rate: {response.status}")
                    return None

        except Exception as e:
            print(f"❌ Lighter funding rate error: {e}")
            return None

    async def close(self):
        """Close client session"""
        # Close aiohttp session if it exists
        if self._session and not self._session.closed:
            await self._session.close()
        # Lighter SDK doesn't require explicit cleanup
