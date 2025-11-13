"""
Lighter DEX client implementation using official SDK
Handles connection and trading operations on Lighter
"""

import asyncio
import time
import json
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
                    # Check for WebSocket support
                    if hasattr(self.client, 'subscribe_account'):
                        print(f"  ✓ WebSocket support available (subscribe_account)")
                    else:
                        print(f"  ⚠ WebSocket not supported (subscribe_account missing)")
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

        # WebSocket client for real-time position monitoring
        self.ws_client = None
        self._ws_task = None
        self._position_update_callbacks = []  # List of callbacks for position updates
        self._ws_running = False

    async def _get_session(self):
        """Get or create aiohttp session"""
        if self._session is None or self._session.closed:
            import aiohttp
            # trust_env=True enables automatic proxy detection from environment variables
            self._session = aiohttp.ClientSession(trust_env=True)
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

    async def get_bid_ask(self, max_retries: int = 5) -> Optional[tuple]:
        """
        Get current bid and ask prices with retry logic

        Note: Lighter doesn't provide orderbook via REST API.
        We use last_trade_price with small estimated spread instead.

        Args:
            max_retries: Maximum number of retry attempts (default 5)

        Returns:
            Tuple of (bid, ask) or None if error
        """
        import aiohttp

        url = f"{self.base_url}/api/v1/orderBookDetails?market={self.market}"
        timeout = aiohttp.ClientTimeout(total=30, connect=10, sock_read=15)

        # Initialize session variable before try block
        session = None

        try:
            # Create a fresh session for each get_bid_ask() call
            # This avoids issues with stale connections
            session = aiohttp.ClientSession()

            for attempt in range(1, max_retries + 1):
                try:
                    async with session.get(url, proxy=self.proxy_url, timeout=timeout) as response:
                        if response.status == 200:
                            data = await response.json()

                            if isinstance(data, dict) and 'order_book_details' in data:
                                for book in data['order_book_details']:
                                    if book.get('symbol', '').upper() == self.market.upper():
                                        last_price = book.get('last_trade_price')

                                        if last_price and float(last_price) > 0:
                                            last_price = float(last_price)
                                            spread_pct = 0.001  # 0.1%
                                            half_spread = last_price * spread_pct / 2
                                            estimated_bid = last_price - half_spread
                                            estimated_ask = last_price + half_spread

                                            if not hasattr(self, '_price_estimation_logged'):
                                                print(f"\nℹ️  Lighter API doesn't provide real-time orderbook via REST")
                                                print(f"   Using last_trade_price with estimated {spread_pct*100}% spread")
                                                print(f"   Last price: ${last_price:.4f}")
                                                print(f"   Estimated bid: ${estimated_bid:.4f}")
                                                print(f"   Estimated ask: ${estimated_ask:.4f}")
                                                self._price_estimation_logged = True

                                            return (estimated_bid, estimated_ask)
                                        else:
                                            if attempt >= max_retries:
                                                print(f"❌ {self.market}: 最終取引価格が無効です")
                                            break  # Exit inner for-loop, proceed to retry

                                # If we finished the for-loop without finding the market
                                else:
                                    if attempt >= max_retries:
                                        print(f"❌ Market '{self.market}' not found in response")

                            else:
                                if attempt >= max_retries:
                                    print(f"❌ Invalid API response structure")
                        else:
                            if attempt >= max_retries:
                                print(f"❌ HTTP {response.status}: APIサーバーエラー")

                    # If we reach here, something went wrong (e.g., non-200 status, invalid data, market not found)
                    # Wait before retrying, unless it's the last attempt.
                    if attempt < max_retries:
                        print(f"   [試行 {attempt}/{max_retries}] 3秒後に再試行します...")
                        await asyncio.sleep(3)
                    continue # Go to next attempt

                except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                    if attempt < max_retries:
                        print(f"⚠️  接続エラー (試行 {attempt}/{max_retries}) - 3秒後に再試行...")
                        await asyncio.sleep(3)
                        continue # Go to next attempt
                    else:
                        print(f"❌ タイムアウト/接続エラー: {max_retries}回の試行後も接続できませんでした。")
                        raise # Re-raise the final exception to be caught by the outer block

        except Exception as e:
            print(f"❌ get_bid_askで予期せぬエラーが発生: {e}")
            import traceback
            traceback.print_exc()

        finally:
            # Always close the session
            try:
                if session and not session.closed:
                    await session.close()
                    # Wait a bit for the connector to finish closing
                    # This prevents "Unclosed client session" warnings
                    await asyncio.sleep(0.25)
            except Exception:
                pass  # Ignore close errors

        # If the loop completes without returning a value, all retries have failed.
        print(f"❌ {self.market} のbid/ask取得に失敗しました ({max_retries}回試行)")
        return None

    async def place_limit_order(self, side: str, size: float, price: float, reduce_only: bool = False) -> Optional[Dict[str, Any]]:
        """
        Place a limit order

        Args:
            side: Order side ('BUY' or 'SELL')
            size: Order size
            price: Limit price
            reduce_only: If True, order will only reduce existing position (for closing positions)

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

            # Debug: Print conversion
            print(f"ℹ️  Order parameters:")
            print(f"   Size: {size} → {base_amount_int} (decimals: {size_decimals})")
            print(f"   Price: {price} → {price_int} (decimals: {price_decimals})")
            print(f"   Market ID: {market_id}")

            # Validate minimum order size (Lighter typically requires minimum $10-20 worth)
            order_value_usd = (base_amount_int / (10 ** size_decimals)) * (price_int / (10 ** price_decimals))
            print(f"   Order value: ${order_value_usd:.2f}")

            if base_amount_int <= 0:
                raise ValueError(f"Invalid base_amount: {base_amount_int} (original size: {size})")
            if price_int <= 0:
                raise ValueError(f"Invalid price: {price_int} (original price: {price})")

            # Check minimum order value
            MIN_ORDER_VALUE_USD = 10.0  # Lighter's typical minimum
            if order_value_usd < MIN_ORDER_VALUE_USD:
                raise ValueError(
                    f"Order value ${order_value_usd:.2f} is below minimum ${MIN_ORDER_VALUE_USD:.2f}. "
                    f"Increase position size or check market configuration."
                )

            print(f"   Reduce only: {reduce_only}")

            # Place limit order using create_order
            tx, tx_hash, err = await self.client.create_order(
                market_index=market_id,
                client_order_index=client_order_index,
                base_amount=base_amount_int,  # Integer
                price=price_int,     # Integer - limit price
                is_ask=(side.upper() == 'SELL'),  # True for SELL, False for BUY
                order_type=lighter.SignerClient.ORDER_TYPE_LIMIT,
                time_in_force=lighter.SignerClient.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
                reduce_only=reduce_only,
                trigger_price=0,
            )

            if err is not None:
                raise Exception(f"Order failed: {err}")

            if not tx_hash:
                print(f"⚠️  警告: tx_hashがNullです！注文が正常に処理されていない可能性があります")

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

    async def place_market_order(self, side: str, size: float, reduce_only: bool = False) -> Optional[Dict[str, Any]]:
        """
        Place a market order

        Args:
            side: Order side ('BUY' or 'SELL')
            size: Order size
            reduce_only: If True, order will only reduce existing position (for closing positions)

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

            print(f"   Reduce only: {reduce_only}")

            # Place market order using create_order with ORDER_TYPE_MARKET
            tx, tx_hash, err = await self.client.create_order(
                market_index=market_id,
                client_order_index=client_order_index,
                base_amount=base_amount_int,  # Integer
                price=price_int,  # Integer - max acceptable price for market orders
                is_ask=(side.upper() == 'SELL'),  # True for SELL, False for BUY
                order_type=lighter.SignerClient.ORDER_TYPE_MARKET,
                time_in_force=lighter.SignerClient.ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL,
                reduce_only=reduce_only,
                trigger_price=0,
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

    async def get_open_orders(self) -> list:
        """
        Get all open (pending) orders from Lighter API

        Returns:
            List of open order IDs, empty list if none or error
        """
        try:
            if not self.client:
                print("      ⚠️  Lighter SDK不使用 - 未約定注文チェックをスキップ")
                return []

            # Use SDK to get account data which includes orders
            api_client = lighter.ApiClient()
            try:
                account_api = lighter.AccountApi(api_client)

                # Add timeout to prevent hanging
                try:
                    account = await asyncio.wait_for(
                        account_api.account(
                            by="index",
                            value=str(self.account_index)
                        ),
                        timeout=10.0  # 10 second timeout
                    )
                except asyncio.TimeoutError:
                    print(f"      ⚠️  API応答タイムアウト (10秒) - 未約定注文チェックをスキップ")
                    return []

                # Convert to dict
                account_dict = account.to_dict() if hasattr(account, 'to_dict') else account

                # Extract open orders from account data
                open_orders = []

                # Check if account has 'accounts' array (SDK response format)
                if isinstance(account_dict, dict):
                    if 'accounts' in account_dict and len(account_dict['accounts']) > 0:
                        account_data = account_dict['accounts'][0]
                    else:
                        account_data = account_dict

                    # Look for orders in various possible locations
                    if 'orders' in account_data:
                        orders = account_data['orders']
                        if isinstance(orders, list):
                            # Filter for open orders (status != filled/cancelled)
                            for order in orders:
                                if isinstance(order, dict):
                                    status = order.get('status', '').lower()
                                    order_id = order.get('order_id') or order.get('id')
                                    # Include orders that are not filled or cancelled
                                    if status not in ['filled', 'cancelled', 'closed'] and order_id:
                                        open_orders.append(str(order_id))

                return open_orders

            finally:
                await api_client.close()

        except Exception as e:
            print(f"      ⚠️  未約定注文の取得エラー: {str(e)[:80]}")
            import traceback
            traceback.print_exc()
            return []

    async def get_account_balance(self, max_retries: int = 3, timeout: float = 30.0) -> Optional[Dict[str, Any]]:
        """
        Get account balance with retry logic and timeout

        Args:
            max_retries: Maximum number of retry attempts (default 3)
            timeout: Timeout in seconds for the API call (default 30.0)

        Returns:
            Account balance or None if error
        """
        import aiohttp

        for attempt in range(1, max_retries + 1):
            try:
                if self.client:
                    api_client = lighter.ApiClient()
                    try:
                        print(f"🔍 [DEBUG] Lighter get_account_balance (試行 {attempt}/{max_retries})...")
                        account_api = lighter.AccountApi(api_client)

                        # Wrap SDK call with timeout to prevent hanging
                        print(f"   [DEBUG] SDK account() 呼び出し中... (timeout={timeout}秒)")
                        account = await asyncio.wait_for(
                            account_api.account(
                                by="index",
                                value=str(self.account_index)
                            ),
                            timeout=timeout
                        )
                        print(f"   [DEBUG] SDK account() 応答受信 ✓")

                        result = account.to_dict() if hasattr(account, 'to_dict') else account
                        return result
                    except asyncio.TimeoutError as e:
                        print(f"   ❌ SDK Timeout ({timeout}秒): アカウント情報取得がタイムアウトしました")
                        if attempt < max_retries:
                            print(f"   リトライ {attempt}/{max_retries}... (2秒待機)")
                            await asyncio.sleep(2)
                            continue
                        raise
                    except aiohttp.ClientError as e:
                        print(f"   ❌ SDK ClientError: {e}")
                        if attempt < max_retries:
                            print(f"   リトライ {attempt}/{max_retries}... (2秒待機)")
                            await asyncio.sleep(2)
                            continue
                        raise
                    finally:
                        await api_client.close()
                else:
                    # Use REST API - public endpoint for account info
                    session = await self._get_session()
                    url = f"{self.base_url}/api/v1/account/{self.account_index}"

                    try:
                        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                            if response.status == 200:
                                result = await response.json()
                                return result
                            else:
                                print(f"ℹ️  Lighter account balance unavailable (SDK required for private data)")
                                return {"status": "SDK_REQUIRED", "message": "Install Lighter SDK for full account access"}
                    except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                        if attempt < max_retries:
                            print(f"❌ REST API Error: {e} - リトライ {attempt}/{max_retries}... (2秒待機)")
                            await asyncio.sleep(2)
                            continue
                        raise

            except Exception as e:
                if attempt < max_retries:
                    print(f"❌ get_account_balance error: {e} - リトライ {attempt}/{max_retries}... (2秒待機)")
                    await asyncio.sleep(2)
                    continue
                print(f"ℹ️  Lighter balance info unavailable: {e} (最終試行)")
                return {"status": "UNAVAILABLE"}

        return {"status": "UNAVAILABLE"}

    async def get_funding_rate(self) -> Optional[Dict[str, Any]]:
        """
        Get current funding rate for the market

        Lighter uses hourly discrete funding with ±0.5% cap per hour

        Returns:
            Dict with funding rate data:
            {
                'funding_rate': float,  # Hourly funding rate (e.g., 0.0001 = 0.01%)
                'funding_rate_pct': float,  # As percentage (e.g., 0.01)
                'next_funding_time': int,  # Unix timestamp
                'market': str
            }
            or None if error
        """
        try:
            session = await self._get_session()

            # Try SDK first if available
            if self.client:
                try:
                    api_client = lighter.ApiClient()
                    try:
                        candlestick_api = lighter.CandlestickApi(api_client)
                        req = lighter.ReqGetFundings(market=self.market, limit=1)
                        fundings = await candlestick_api.fundings(req)

                        if fundings and hasattr(fundings, 'fundings') and len(fundings.fundings) > 0:
                            latest = fundings.fundings[0]
                            funding_rate = float(latest.funding_rate) if hasattr(latest, 'funding_rate') else 0

                            return {
                                'funding_rate': funding_rate,
                                'funding_rate_pct': funding_rate * 100,
                                'next_funding_time': getattr(latest, 'timestamp', 0),
                                'market': self.market,
                                'source': 'SDK'
                            }
                    finally:
                        await api_client.close()
                except Exception as sdk_error:
                    print(f"ℹ️  SDK funding rate query failed, falling back to REST API: {sdk_error}")

            # Fallback to REST API
            url = f"{self.base_url}/api/v1/fundings?market={self.market}&limit=1"

            async with session.get(url, proxy=self.proxy_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    data = await response.json()

                    # Parse response - structure may be {"fundings": [...]} or direct array
                    fundings_list = data.get('fundings', data) if isinstance(data, dict) else data

                    if fundings_list and len(fundings_list) > 0:
                        latest = fundings_list[0]
                        funding_rate = float(latest.get('funding_rate', 0))

                        return {
                            'funding_rate': funding_rate,
                            'funding_rate_pct': funding_rate * 100,
                            'next_funding_time': latest.get('timestamp', 0),
                            'market': self.market,
                            'source': 'REST'
                        }
                    else:
                        print(f"⚠️  No funding rate data available for {self.market}")
                        return None
                else:
                    print(f"❌ Failed to fetch funding rate: HTTP {response.status}")
                    return None

        except Exception as e:
            print(f"❌ Error fetching Lighter funding rate: {e}")
            import traceback
            traceback.print_exc()
            return None


    async def cancel_order(self, order_id: str, silent: bool = False) -> bool:
        """
        Cancel an order

        Args:
            order_id: Order ID
            silent: If True, suppress error messages (useful for cleanup)

        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.client:
                if not silent:
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

            if not silent:
                print(f"✓ Lighter order cancelled: {order_id}")
            return True

        except Exception as e:
            if not silent:
                print(f"❌ Lighter cancel error: {e}")
            return False

    async def cancel_all_orders(self, silent: bool = False) -> bool:
        """
        Cancel ALL open orders (CRITICAL safety feature)

        This uses the cancel_all_orders SDK method to ensure ALL pending orders
        are cancelled before placing new orders. This is MANDATORY to prevent
        multiple orders from filling simultaneously.

        Args:
            silent: If True, suppress output messages

        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.client:
                if not silent:
                    print("❌ Lighter SDK required for canceling orders")
                return False

            # Create auth token
            auth, err = self.client.create_auth_token_with_expiry(
                lighter.SignerClient.DEFAULT_10_MIN_AUTH_EXPIRY
            )
            if err is not None:
                raise Exception(f"Failed to create auth token: {err}")

            if not silent:
                print(f"🗑️  【CRITICAL】全未約定注文を一括キャンセル中...")

            # Cancel ALL orders
            # This ensures cancellation of all pending orders
            tx, tx_hash, err = await self.client.cancel_all_orders()

            if err is not None:
                raise Exception(f"Cancel all failed: {err}")

            if not silent:
                print(f"   ✅ 全注文キャンセル完了")
                print(f"   TX Hash: {tx_hash}")

            return True

        except Exception as e:
            if not silent:
                print(f"❌ Cancel all orders error: {e}")
            return False

    async def subscribe_to_account_updates(self, callback):
        """
        Subscribe to account updates via WebSocket

        Args:
            callback: Async function to call when account data is received
                     Should accept a single parameter: account data dict

        Raises:
            AttributeError: If subscribe_account method is not available in SDK
        """
        if not self.client:
            raise AttributeError("Lighter SDK client not available")

        # Check if subscribe_account method exists
        if not hasattr(self.client, 'subscribe_account'):
            raise AttributeError("subscribe_account method not available in Lighter SDK")

        try:
            print(f"🔌 Subscribing to account updates for index {self.account_index}...")

            # Subscribe to account updates using Lighter SDK
            async for account_data in self.client.subscribe_account(
                account_index=self.account_index
            ):
                try:
                    # Parse account data
                    if hasattr(account_data, 'to_dict'):
                        account_dict = account_data.to_dict()
                    elif isinstance(account_data, dict):
                        account_dict = account_data
                    else:
                        account_dict = vars(account_data)

                    # Debug: Print full account structure on first receive
                    if not hasattr(self, '_account_structure_logged'):
                        print(f"\n📊 Account Structure (first update):")
                        print(json.dumps(account_dict, indent=2, default=str))
                        self._account_structure_logged = True

                    # Call the callback with account data
                    await callback(account_dict)

                except Exception as e:
                    print(f"❌ Error processing account update: {e}")
                    import traceback
                    traceback.print_exc()

        except AttributeError:
            # Re-raise AttributeError so caller can handle it
            raise
        except Exception as e:
            print(f"❌ WebSocket subscription error: {e}")
            import traceback
            traceback.print_exc()
            raise

    async def get_position_from_account(self, account_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract position information from account data

        Args:
            account_data: Account data dict from WebSocket or API

        Returns:
            Position dict with size, entry_price, etc., or None if no position
        """
        try:
            # Get market_id for current market
            market_id = await self._get_market_id_from_api(self.market)
            if market_id is None:
                return None

            # Handle SDK response format: {code: 200, accounts: [{...}]}
            if 'accounts' in account_data and isinstance(account_data['accounts'], list):
                if len(account_data['accounts']) > 0:
                    account = account_data['accounts'][0]
                    # Recursively process the actual account object
                    return await self.get_position_from_account(account)

            # Check for perp_positions key (most likely location)
            if 'perp_positions' in account_data:
                perp_positions = account_data['perp_positions']

                # Find position for our market
                if isinstance(perp_positions, dict):
                    position = perp_positions.get(str(market_id))
                    if position:
                        return self._parse_position(position)

                elif isinstance(perp_positions, list):
                    for pos in perp_positions:
                        if isinstance(pos, dict) and pos.get('market_id') == market_id:
                            return self._parse_position(pos)

            # Fallback: Check positions array (if it exists)
            if 'positions' in account_data:
                positions = account_data['positions']

                if isinstance(positions, list):
                    for pos in positions:
                        if isinstance(pos, dict):
                            pos_market_id = pos.get('market_id')
                            # market_idが一致するかチェック（数値と文字列両方を試す）
                            if pos_market_id == market_id or pos_market_id == str(market_id):
                                return self._parse_position(pos)
                        elif isinstance(pos, int) and pos == market_id:
                            # positions array contains only market IDs - need to fetch full data
                            full_account = await self.get_account_balance()
                            if full_account:
                                return await self.get_position_from_account(full_account)

            # Fallback 2: Check other possible keys
            for possible_key in ['perp_position', 'perpetual_positions', 'perpetual_position', 'account_positions']:
                if possible_key in account_data:
                    value = account_data[possible_key]
                    if isinstance(value, dict):
                        # Try to find position by market_id
                        pos = value.get(str(market_id))
                        if pos:
                            return self._parse_position(pos)
                    elif isinstance(value, list):
                        for pos in value:
                            if isinstance(pos, dict) and pos.get('market_id') == market_id:
                                return self._parse_position(pos)

            # No position found
            return None

        except Exception as e:
            print(f"❌ Error extracting position from account data: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _parse_position(self, position_data: Any) -> Optional[Dict[str, Any]]:
        """
        Parse position data into standard format

        Args:
            position_data: Raw position data (dict or object)

        Returns:
            Standardized position dict, or None if position size is 0
        """
        if hasattr(position_data, 'to_dict'):
            pos = position_data.to_dict()
        elif isinstance(position_data, dict):
            pos = position_data
        else:
            pos = vars(position_data)

        # Extract key fields
        # Lighter API uses 'position' field, not 'size'
        position_str = pos.get('position', '0')
        size = float(position_str) if position_str else 0.0

        # If size is still 0, try other possible fields
        if size == 0:
            size = float(pos.get('size', 0) or pos.get('base_amount', 0) or 0)

        # Apply sign (1 for long, -1 for short)
        sign = int(pos.get('sign', 1))
        size = size * sign

        # If position size is 0, return None (no actual position)
        if abs(size) < 0.0001:  # Allow for floating point precision
            return None

        entry_price = float(pos.get('entry_price', 0) or pos.get('avg_entry_price', 0) or 0)
        market_id = pos.get('market_id', None)

        return {
            'size': size,
            'entry_price': entry_price,
            'market_id': market_id,
            'symbol': pos.get('symbol', ''),
            'raw': pos  # Keep raw data for debugging
        }

    async def start_websocket(self, on_position_update_callback=None):
        """
        Start WebSocket connection for real-time position monitoring

        Args:
            on_position_update_callback: Optional callback function(account_data) to call on account updates
        """
        if not LIGHTER_SDK_AVAILABLE:
            print("⚠️  WebSocket requires Lighter SDK - not available")
            return False

        if self._ws_running:
            print("⚠️  WebSocket already running")
            return True

        try:
            # Register callback if provided
            if on_position_update_callback:
                self._position_update_callbacks.append(on_position_update_callback)

            # Create WebSocket client
            print(f"\n🔌 WebSocket接続を開始中...")
            print(f"   アカウントID: {self.account_index}")

            self.ws_client = lighter.WsClient(
                account_ids=[self.account_index],
                on_account_update=self._on_account_update,
            )

            # Start WebSocket in background task
            self._ws_running = True
            self._ws_task = asyncio.create_task(self._run_websocket())

            print(f"✅ WebSocket接続開始成功")
            return True

        except Exception as e:
            print(f"❌ WebSocket接続失敗: {e}")
            self._ws_running = False
            return False

    async def _run_websocket(self):
        """Run WebSocket client (internal method)"""
        try:
            if self.ws_client:
                # Use run_async() method for async WebSocket connection
                await self.ws_client.run_async()
        except Exception as e:
            print(f"❌ WebSocket実行エラー: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._ws_running = False

    def _on_account_update(self, account_id: int, account_state: dict):
        """
        Callback for WebSocket account updates (SYNCHRONOUS)

        SDK calls this synchronously as: on_account_update(account_id, account_state)
        We need to schedule async processing in the background

        Args:
            account_id: Account ID from WebSocket
            account_state: Account state data from WebSocket
        """
        # Schedule async processing in background
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Create task in background
                asyncio.create_task(self._process_account_update(account_state))
            else:
                # If no loop running, run synchronously (should not happen in normal operation)
                print(f"⚠️  [WebSocket] イベントループが実行されていません")
        except Exception as e:
            print(f"⚠️  [WebSocket] タスク作成エラー: {e}")
            import traceback
            traceback.print_exc()

    async def _process_account_update(self, account_data: dict):
        """
        Process account update asynchronously (called from _on_account_update)

        Args:
            account_data: Account data from WebSocket
        """
        try:
            # Process position from account data
            position = await self.get_position_from_account(account_data)

            if position:
                print(f"\n📊 [WebSocket] ポジション更新検知:")
                print(f"   サイズ: {position.get('size', 0):.2f}")
                print(f"   エントリー価格: {position.get('entry_price', 0):.4f}")

            # Call registered callbacks
            for callback in self._position_update_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(account_data)
                    else:
                        callback(account_data)
                except Exception as e:
                    print(f"⚠️  コールバックエラー: {e}")

        except Exception as e:
            print(f"⚠️  アカウント更新処理エラー: {e}")
            import traceback
            traceback.print_exc()

    async def stop_websocket(self):
        """Stop WebSocket connection"""
        if not self._ws_running:
            return

        print(f"\n🔌 WebSocket接続を停止中...")
        self._ws_running = False

        # Cancel WebSocket task
        if self._ws_task and not self._ws_task.done():
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass

        self.ws_client = None
        self._ws_task = None
        print(f"✅ WebSocket接続停止完了")

    def add_position_update_callback(self, callback):
        """
        Add a callback for position updates

        Args:
            callback: Function(account_data) to call on position updates
        """
        if callback not in self._position_update_callbacks:
            self._position_update_callbacks.append(callback)

    def remove_position_update_callback(self, callback):
        """Remove a position update callback"""
        if callback in self._position_update_callbacks:
            self._position_update_callbacks.remove(callback)

    async def close(self):
        """Close client session"""
        # Stop WebSocket if running
        if self._ws_running:
            await self.stop_websocket()

        # Close aiohttp session if it exists
        if self._session and not self._session.closed:
            await self._session.close()
            # Wait a bit longer for the connector to finish closing
            # This prevents "Unclosed connector" warnings
            import asyncio
            await asyncio.sleep(1.0)
        # Lighter SDK doesn't require explicit cleanup
