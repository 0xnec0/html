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

        # WebSocket client and state
        self._ws_client = None
        self._ws_running = False
        self._latest_orderbook = None  # Latest orderbook from WebSocket
        self._latest_account = None  # Latest account from WebSocket
        self._position_event = asyncio.Event()  # Event for position changes
        self._initial_position_size = None  # Track initial position size

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

            print(f"ℹ️  Placing LIMIT order:")
            print(f"   Price: {price} → {price_int} (decimals: {price_decimals})")
            print(f"   Size: {size} → {base_amount_int} (decimals: {size_decimals})")

            # Place true limit order using create_order with ORDER_TYPE_LIMIT
            tx, tx_hash, err = await self.client.create_order(
                market_index=market_id,
                client_order_index=client_order_index,
                base_amount=base_amount_int,  # Integer - order size
                price=price_int,  # Integer - limit price
                is_ask=(side.upper() == 'SELL'),  # True for SELL, False for BUY
                order_type=lighter.SignerClient.ORDER_TYPE_LIMIT,  # Limit order type
                time_in_force=lighter.SignerClient.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
                reduce_only=False,
                trigger_price=0,
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
        Deprecated: Use _get_market_id_from_api() instead for dynamic lookup
        """
        # Market indices from Lighter protocol
        # These should be verified via /api/v1/orderBookDetails
        market_indices = {
            'ETH': 0,
            'BTC': 1,
            'DOGE': 2,
            'JUP': 3,  # Jupiter
            'SOL': 4,
            'ENA': 5,  # Ethena - verify actual index
        }
        index = market_indices.get(market.upper(), None)
        if index is None:
            print(f"⚠ Unknown market {market}, attempting dynamic lookup...")
            # Try to get from cache
            if market in self._market_id_cache:
                return self._market_id_cache[market]
            print(f"⚠ Market {market} not found in cache, defaulting to index 0")
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

            # Get market_id dynamically (preferred) or use fallback
            market_id = await self._get_market_id_from_api(self.market)
            if market_id is None:
                print(f"⚠️  Using fallback market index for {self.market}")
                market_id = self._get_market_index(self.market)

            # Cancel order
            tx, tx_hash, err = await self.client.cancel_order(
                market_index=market_id,
                order_index=int(order_id)
            )

            if err is not None:
                raise Exception(f"Cancel failed: {err}")

            print(f"✓ Lighter order cancelled: {order_id}")
            return True

        except Exception as e:
            print(f"❌ Lighter cancel error: {e}")
            return False

    async def get_position(self) -> Optional[Dict[str, Any]]:
        """
        Get current position for the market

        Returns:
            Position info with size, entry_price, etc. or None if no position/error
        """
        try:
            if self.client:
                # Use SDK to get account info
                api_client = lighter.ApiClient()
                try:
                    account_api = lighter.AccountApi(api_client)
                    account = await account_api.account(
                        by="index",
                        value=str(self.account_index)
                    )

                    # Convert to dict if needed
                    account_dict = account.to_dict() if hasattr(account, 'to_dict') else account

                    # Get market_id for this market
                    market_id = await self._get_market_id_from_api(self.market)

                    # Look for position in the account data
                    if isinstance(account_dict, dict):
                        # Check for positions array
                        positions = account_dict.get('positions', [])
                        if positions:
                            for pos in positions:
                                if pos.get('market_id') == market_id or pos.get('market') == self.market.upper():
                                    size = float(pos.get('size', 0))
                                    if abs(size) > 0:
                                        return {
                                            'size': size,
                                            'entry_price': float(pos.get('entry_price', 0)),
                                            'market': self.market,
                                            'market_id': market_id
                                        }

                        # Alternative: check perp_positions
                        perp_positions = account_dict.get('perp_positions', [])
                        if perp_positions:
                            for pos in perp_positions:
                                if pos.get('market_id') == market_id or pos.get('symbol') == self.market.upper():
                                    size = float(pos.get('size', 0) or pos.get('amount', 0))
                                    if abs(size) > 0:
                                        return {
                                            'size': size,
                                            'entry_price': float(pos.get('entry_price', 0) or pos.get('avg_entry_price', 0)),
                                            'market': self.market,
                                            'market_id': market_id
                                        }

                    # No position found
                    return None

                finally:
                    await api_client.close()
            else:
                # Use REST API fallback
                session = await self._get_session()
                url = f"{self.base_url}/api/v1/account/{self.account_index}"

                async with session.get(url, proxy=self.proxy_url) as response:
                    if response.status == 200:
                        data = await response.json()

                        # Get market_id for this market
                        market_id = await self._get_market_id_from_api(self.market)

                        # Check positions
                        if 'positions' in data:
                            for pos in data['positions']:
                                if pos.get('market_id') == market_id:
                                    size = float(pos.get('size', 0))
                                    if abs(size) > 0:
                                        return {
                                            'size': size,
                                            'entry_price': float(pos.get('entry_price', 0)),
                                            'market': self.market,
                                            'market_id': market_id
                                        }

                        return None
                    else:
                        print(f"⚠️  Failed to fetch position: HTTP {response.status}")
                        return None

        except Exception as e:
            print(f"⚠️  Error getting position: {e}")
            return None

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

    async def place_limit_order_with_spread_check(
        self,
        side: str,
        size: float,
        max_spread_pct: float = 0.03,
        check_interval: float = 2.0,
        timeout: float = 60.0
    ) -> Optional[Dict[str, Any]]:
        """
        Place limit order when spread is within acceptable range

        Args:
            side: Order side ('BUY' or 'SELL')
            size: Order size
            max_spread_pct: Maximum spread in percentage (e.g., 0.03 for 0.03%)
            check_interval: How often to check spread in seconds
            timeout: How long to wait for acceptable spread (0 = infinite)

        Returns:
            Order result if placed, None if timeout or error
        """
        print(f"\n📊 Lighter: スプレッドチェック付き指値注文")
        print(f"   Side: {side} | Size: {size}")
        print(f"   最大スプレッド: {max_spread_pct}%")
        print(f"   タイムアウト: {timeout}秒" if timeout > 0 else "   タイムアウト: なし（無限）")

        start_time = asyncio.get_event_loop().time()
        check_count = 0

        while True:
            check_count += 1

            # Get current bid/ask
            bid_ask = await self.get_bid_ask()
            if not bid_ask:
                print(f"\r   [{check_count}] ❌ 価格取得失敗、リトライ中...", end='', flush=True)
                await asyncio.sleep(check_interval)
                continue

            bid, ask = bid_ask
            mid = (bid + ask) / 2
            spread = abs(ask - bid)
            spread_pct = (spread / mid) * 100

            elapsed = asyncio.get_event_loop().time() - start_time
            print(f"\r   [{check_count}] スプレッド: {spread_pct:.4f}% | 経過: {elapsed:.0f}秒", end='', flush=True)

            # Check if spread is acceptable
            if spread_pct <= max_spread_pct:
                print(f"\n✅ スプレッド条件達成！ {spread_pct:.4f}% ≤ {max_spread_pct}%")
                print(f"   Bid: ${bid:.4f} | Ask: ${ask:.4f}")

                # Determine limit price based on side
                # For BUY: use best bid (to get filled faster)
                # For SELL: use best ask (to get filled faster)
                if side.upper() == 'BUY':
                    limit_price = bid
                    print(f"   指値価格: ${limit_price:.4f} (Best Bid)")
                else:
                    limit_price = ask
                    print(f"   指値価格: ${limit_price:.4f} (Best Ask)")

                # Place limit order
                result = await self.place_limit_order(side, size, limit_price)
                return result

            # Check timeout
            if timeout > 0 and elapsed >= timeout:
                print(f"\n⏰ タイムアウト: スプレッド条件未達成")
                print(f"   現在のスプレッド: {spread_pct:.4f}% > {max_spread_pct}%")
                return None

            # Wait before next check
            await asyncio.sleep(check_interval)

    async def wait_for_order_fill(
        self,
        order_id: int,
        check_interval: float = 2.0,
        timeout: float = 60.0
    ) -> bool:
        """
        Wait for order to be filled

        Args:
            order_id: Order ID to check
            check_interval: How often to check in seconds
            timeout: How long to wait (0 = infinite)

        Returns:
            True if order filled, False if timeout or error
        """
        print(f"\n⏳ Lighter: 約定待機中...")
        print(f"   Order ID: {order_id}")
        print(f"   Market: {self.market}")
        print(f"   チェック間隔: {check_interval}秒")
        print(f"   タイムアウト: {timeout}秒" if timeout > 0 else "   タイムアウト: なし（無限）")

        start_time = asyncio.get_event_loop().time()
        check_count = 0
        last_position_info = None

        # Get initial position (if any)
        try:
            initial_position = await self.get_position()
            initial_size = abs(initial_position.get('size', 0)) if initial_position else 0
            print(f"   初期ポジション: {initial_size}")
        except Exception as e:
            print(f"   初期ポジション取得エラー: {e}")
            initial_size = 0

        while True:
            check_count += 1
            elapsed = asyncio.get_event_loop().time() - start_time

            # For Lighter, we'll check position to see if order was filled
            try:
                position = await self.get_position()
                current_size = abs(position.get('size', 0)) if position else 0

                # Show detailed position info every 10 checks
                if check_count % 10 == 0 or (position and current_size > initial_size):
                    position_info = f"Position: {current_size} (initial: {initial_size})"
                    if position:
                        position_info += f" | Entry: ${position.get('entry_price', 0):.4f}"
                    print(f"\n   [{check_count}] {position_info} | 経過: {elapsed:.0f}秒")
                    last_position_info = position

                # Check if position increased (order filled)
                if position and current_size > initial_size:
                    print(f"\n✅ 約定確認！ポジション増加検出")
                    print(f"   初期サイズ: {initial_size}")
                    print(f"   現在サイズ: {current_size}")
                    print(f"   約定サイズ: {current_size - initial_size}")
                    if position.get('entry_price'):
                        print(f"   エントリー価格: ${position.get('entry_price'):.4f}")
                    return True

                # Normal progress indicator
                if check_count % 10 != 0:
                    print(f"\r   [{check_count}] 約定待ち... (現在サイズ: {current_size}) | 経過: {elapsed:.0f}秒", end='', flush=True)

            except Exception as e:
                if check_count % 10 == 0:
                    print(f"\n   [{check_count}] ポジション確認エラー: {e} | 経過: {elapsed:.0f}秒")
                else:
                    print(f"\r   [{check_count}] チェック中... | 経過: {elapsed:.0f}秒", end='', flush=True)

            # Check timeout
            if timeout > 0 and elapsed >= timeout:
                print(f"\n⏰ タイムアウト: 約定未確認")
                print(f"   最終ポジションサイズ: {current_size if 'current_size' in locals() else 'N/A'}")
                if last_position_info:
                    print(f"   最終ポジション情報: {last_position_info}")
                return False

            # Wait before next check
            await asyncio.sleep(check_interval)

    async def place_limit_order_with_spread_check_ws(
        self,
        side: str,
        size: float,
        max_spread_pct: float = 0.03,
        timeout: float = 60.0
    ) -> Optional[Dict[str, Any]]:
        """
        Place limit order when spread is within acceptable range (WebSocket version)
        Uses real-time WebSocket orderbook updates instead of polling

        Args:
            side: Order side ('BUY' or 'SELL')
            size: Order size
            max_spread_pct: Maximum spread in percentage (e.g., 0.03 for 0.03%)
            timeout: How long to wait for acceptable spread (0 = infinite)

        Returns:
            Order result if placed, None if timeout or error
        """
        print(f"\n📊 Lighter: スプレッドチェック付き指値注文 (WebSocket)")
        print(f"   Side: {side} | Size: {size}")
        print(f"   最大スプレッド: {max_spread_pct}%")
        print(f"   タイムアウト: {timeout}秒" if timeout > 0 else "   タイムアウト: なし（無限）")

        # Ensure WebSocket is running
        if not self._ws_running:
            success = await self.start_websocket()
            if not success:
                print("⚠️  WebSocket起動失敗、ポーリング方式にフォールバック")
                return await self.place_limit_order_with_spread_check(side, size, max_spread_pct, 2.0, timeout)

        start_time = asyncio.get_event_loop().time()
        check_count = 0

        while True:
            check_count += 1

            # Get latest orderbook from WebSocket
            if self._latest_orderbook:
                bids = self._latest_orderbook.get('bids', [])
                asks = self._latest_orderbook.get('asks', [])

                if bids and asks:
                    bid = float(bids[0]['price']) if bids[0].get('price') else None
                    ask = float(asks[0]['price']) if asks[0].get('price') else None

                    if bid and ask:
                        mid = (bid + ask) / 2
                        spread = abs(ask - bid)
                        spread_pct = (spread / mid) * 100

                        elapsed = asyncio.get_event_loop().time() - start_time
                        print(f"\r   [{check_count}] スプレッド: {spread_pct:.4f}% | 経過: {elapsed:.0f}秒", end='', flush=True)

                        # Check if spread is acceptable
                        if spread_pct <= max_spread_pct:
                            print(f"\n✅ スプレッド条件達成！ {spread_pct:.4f}% ≤ {max_spread_pct}%")
                            print(f"   Bid: ${bid:.4f} | Ask: ${ask:.4f}")

                            # Determine limit price
                            if side.upper() == 'BUY':
                                limit_price = bid
                                print(f"   指値価格: ${limit_price:.4f} (Best Bid)")
                            else:
                                limit_price = ask
                                print(f"   指値価格: ${limit_price:.4f} (Best Ask)")

                            # Place limit order
                            result = await self.place_limit_order(side, size, limit_price)
                            return result

            # Check timeout
            elapsed = asyncio.get_event_loop().time() - start_time
            if timeout > 0 and elapsed >= timeout:
                print(f"\n⏰ タイムアウト: スプレッド条件未達成")
                return None

            # Wait a bit before checking again
            await asyncio.sleep(0.1)  # WebSocket is real-time, so short wait

    async def wait_for_order_fill_ws(
        self,
        order_id: int,
        initial_size: float = 0,
        timeout: float = 60.0
    ) -> bool:
        """
        Wait for order to be filled (WebSocket version)
        Uses real-time account updates instead of polling

        Args:
            order_id: Order ID to check
            initial_size: Initial position size before order
            timeout: How long to wait (0 = infinite)

        Returns:
            True if order filled, False if timeout or error
        """
        print(f"\n⏳ Lighter: 約定待機中 (WebSocket)...")
        print(f"   Order ID: {order_id}")
        print(f"   初期サイズ: {initial_size}")
        print(f"   タイムアウト: {timeout}秒" if timeout > 0 else "   タイムアウト: なし（無限）")

        # Ensure WebSocket is running
        if not self._ws_running:
            success = await self.start_websocket()
            if not success:
                print("⚠️  WebSocket起動失敗、ポーリング方式にフォールバック")
                return await self.wait_for_order_fill(order_id, 2.0, timeout)

        # Set initial position size for tracking
        self._initial_position_size = initial_size
        self._position_event.clear()

        start_time = asyncio.get_event_loop().time()

        try:
            # Wait for position event or timeout
            while True:
                # Check if position changed
                if self._position_event.is_set():
                    print(f"\n✅ 約定確認！(WebSocket)")
                    return True

                # Check timeout
                elapsed = asyncio.get_event_loop().time() - start_time
                if timeout > 0 and elapsed >= timeout:
                    print(f"\n⏰ タイムアウト: 約定未確認 ({elapsed:.0f}秒)")
                    return False

                # Show progress
                if int(elapsed) % 10 == 0:
                    print(f"\r   約定待機中... | 経過: {elapsed:.0f}秒", end='', flush=True)

                # Short wait before checking again
                await asyncio.sleep(1.0)

        finally:
            # Reset tracking
            self._initial_position_size = None
            self._position_event.clear()

    async def start_websocket(self):
        """
        Start WebSocket connection for real-time updates
        Subscribes to orderbook and account updates
        """
        if not LIGHTER_SDK_AVAILABLE or not self.client:
            print("⚠️  WebSocket requires Lighter SDK")
            return False

        try:
            # Get market_id for this market
            market_id = await self._get_market_id_from_api(self.market)
            if market_id is None:
                print(f"❌ Could not find market_id for {self.market}")
                return False

            print(f"\n🔌 Starting WebSocket connection...")
            print(f"   Market ID: {market_id} ({self.market})")
            print(f"   Account Index: {self.account_index}")

            # Create WebSocket client
            self._ws_client = lighter.WsClient(
                order_book_ids=[market_id],
                account_ids=[self.account_index],
                on_order_book_update=self._on_orderbook_update,
                on_account_update=self._on_account_update,
            )

            # Start WebSocket in background task
            self._ws_running = True
            asyncio.create_task(self._run_websocket())

            print(f"✅ WebSocket connected")
            return True

        except Exception as e:
            print(f"❌ WebSocket connection failed: {e}")
            return False

    async def _run_websocket(self):
        """Background task to run WebSocket client"""
        try:
            await self._ws_client.run_async()
        except Exception as e:
            print(f"⚠️  WebSocket error: {e}")
        finally:
            self._ws_running = False

    def _on_orderbook_update(self, market_id: int, orderbook: Dict[str, Any]):
        """
        Callback for orderbook updates from WebSocket

        Args:
            market_id: Market ID
            orderbook: Orderbook data with bids and asks
        """
        self._latest_orderbook = orderbook
        # Debug: print bid/ask spread occasionally
        if hasattr(self, '_ob_update_count'):
            self._ob_update_count += 1
        else:
            self._ob_update_count = 1

        if self._ob_update_count % 100 == 0:  # Print every 100 updates
            bids = orderbook.get('bids', [])
            asks = orderbook.get('asks', [])
            if bids and asks:
                best_bid = float(bids[0]['price']) if bids[0].get('price') else 0
                best_ask = float(asks[0]['price']) if asks[0].get('price') else 0
                if best_bid and best_ask:
                    spread = (best_ask - best_bid) / ((best_bid + best_ask) / 2) * 100
                    print(f"\n📊 WS Update #{self._ob_update_count}: Bid ${best_bid:.4f} | Ask ${best_ask:.4f} | Spread {spread:.4f}%")

    def _on_account_update(self, account_id: int, account: Dict[str, Any]):
        """
        Callback for account updates from WebSocket

        Args:
            account_id: Account ID
            account: Account data with positions
        """
        self._latest_account = account

        # Check for position changes
        positions = account.get('positions', []) or account.get('perp_positions', [])
        if positions:
            for pos in positions:
                size = abs(float(pos.get('size', 0) or pos.get('amount', 0)))
                if size > 0:
                    # Position detected - check if it changed
                    if self._initial_position_size is not None:
                        if size > self._initial_position_size:
                            print(f"\n✅ WS: Position change detected! {self._initial_position_size} → {size}")
                            self._position_event.set()  # Signal position change
                    break

    async def stop_websocket(self):
        """Stop WebSocket connection"""
        self._ws_running = False
        if self._ws_client:
            # WsClient will stop when run_async() completes
            print("🔌 Stopping WebSocket...")
            self._ws_client = None

    async def close(self):
        """Close client session"""
        # Stop WebSocket first
        await self.stop_websocket()

        # Close aiohttp session if it exists
        if self._session and not self._session.closed:
            await self._session.close()
        # Lighter SDK doesn't require explicit cleanup
