"""
Paradex DEX client implementation
Handles connection and trading operations on Paradex
"""

import asyncio
import aiohttp
import json
import time
import hashlib
import hmac
import math
from typing import Dict, Any, Optional
from eth_account import Account
from eth_account.messages import encode_defunct

# Try to import SDK, but make it optional
try:
    from paradex_py import Paradex
    from paradex_py.common.order import Order, OrderSide, OrderType
    from decimal import Decimal
    PARADEX_SDK_AVAILABLE = True
except ImportError:
    PARADEX_SDK_AVAILABLE = False
    print("⚠ Paradex SDK not available, using REST API")


class ParadexClient:
    """Client for interacting with Paradex DEX"""

    def __init__(self, env: str, l1_address: str, l1_private_key: str, market: str = "DOGE-USD-PERP",
                 l2_address: str = None, l2_private_key: str = None, proxy_url: str = None):
        """
        Initialize Paradex client

        Args:
            env: Environment (TESTNET or MAINNET)
            l1_address: Ethereum L1 address
            l1_private_key: Ethereum L1 private key
            market: Trading market symbol
            l2_address: Optional L2 address (for existing accounts)
            l2_private_key: Optional L2 private key (for existing accounts)
            proxy_url: Proxy URL with authentication (optional)
        """
        self.market = market
        self.l1_address = l1_address
        self.l1_private_key = l1_private_key
        self.l2_address = l2_address
        self.l2_private_key = l2_private_key
        self.env_name = env.upper()
        self.proxy_url = proxy_url

        # Set API base URL
        if self.env_name == "TESTNET":
            self.base_url = "https://api.testnet.paradex.trade/v1"
        else:
            self.base_url = "https://api.prod.paradex.trade/v1"

        # Try SDK initialization if available
        self.client = None
        self.account = None

        if PARADEX_SDK_AVAILABLE:
            try:
                # Environment is a string: "testnet" or "prod"
                env_str = "testnet" if self.env_name == "TESTNET" else "prod"

                # Use L2 authentication if L2 private key provided
                if l2_private_key:
                    # L2 authentication: requires Ethereum L1 address + L2 private key
                    if not l1_address:
                        raise ValueError("L2 authentication requires PARADEX_L1_ADDRESS (Ethereum address)")
                    self.client = Paradex(
                        env=env_str,
                        l1_address=l1_address,  # Ethereum L1 address (42 chars)
                        l2_private_key=l2_private_key  # L2 private key
                    )
                    print(f"✓ Paradex initialized with L2 SDK")
                    print(f"  L1 Address: {l1_address}")
                    print(f"  Using L2 private key for authentication")
                elif l1_address and l1_private_key:
                    # L1 authentication (for new accounts)
                    self.client = Paradex(
                        env=env_str,
                        l1_address=l1_address,
                        l1_private_key=l1_private_key
                    )
                    print(f"✓ Paradex initialized with L1 SDK")
                    print(f"  L1 Address: {l1_address}")
                else:
                    raise ValueError("Either L1 or L2 credentials required")
            except Exception as e:
                print(f"⚠ SDK init failed: {e}")
                self.client = None

        # If SDK is not available or failed, try REST API with L1 credentials
        if not self.client:
            # L2-only authentication requires SDK
            if l2_address and l2_private_key and not l1_private_key:
                raise ValueError(
                    "❌ L2-only authentication requires Paradex SDK!\n"
                    "   Please install it: pip install paradex-py\n"
                    "   Or provide L1 credentials for REST API mode."
                )

            # REST API requires L1 credentials
            if not l1_private_key:
                raise ValueError(
                    "❌ REST API mode requires L1 private key!\n"
                    "   Please install Paradex SDK for L2 authentication: pip install paradex-py\n"
                    "   Or provide L1 credentials in your .env file."
                )

            self.account = Account.from_key(l1_private_key)
            print(f"✓ Paradex initialized with REST API")
            print(f"  Address: {self.l1_address}")

        print(f"  Market: {self.market}")

        # HTTP session for REST API calls (will be created on first use)
        self._session = None

    async def _get_session(self):
        """Get or create aiohttp session"""
        if self._session is None or self._session.closed:
            # trust_env=True enables automatic proxy detection from environment variables
            self._session = aiohttp.ClientSession(trust_env=True)
        return self._session

    async def _make_request(self, method: str, endpoint: str, data: Dict = None, signed: bool = False) -> Optional[Dict[str, Any]]:
        """
        Make HTTP request to Paradex API

        Args:
            method: HTTP method
            endpoint: API endpoint
            data: Request data
            signed: Whether to sign the request

        Returns:
            Response data or None
        """
        url = f"{self.base_url}{endpoint}"
        headers = {"Content-Type": "application/json"}

        if signed:
            timestamp = str(int(time.time() * 1000))
            headers["X-API-Timestamp"] = timestamp
            headers["X-API-Key"] = self.l1_address

            # Create signature
            message = f"{timestamp}{method}{endpoint}"
            if data:
                message += json.dumps(data, separators=(',', ':'))

            signature = self.account.sign_message(encode_defunct(text=message))
            headers["X-API-Signature"] = signature.signature.hex()

        try:
            session = await self._get_session()
            if method == "GET":
                async with session.get(url, headers=headers, proxy=self.proxy_url) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        error_text = await response.text()
                        print(f"❌ Paradex API error: {response.status} - {error_text}")
                        return None
            elif method == "POST":
                async with session.post(url, json=data, headers=headers, proxy=self.proxy_url) as response:
                    if response.status in [200, 201]:
                        return await response.json()
                    else:
                        error_text = await response.text()
                        print(f"❌ Paradex API error: {response.status} - {error_text}")
                        return None
        except Exception as e:
            print(f"❌ Paradex request error: {e}")
            return None

    async def get_market_price(self) -> Optional[float]:
        """
        Get current market price

        Returns:
            Current market price or None if error
        """
        try:
            # Try SDK first
            if self.client:
                summary = self.client.api_client.fetch_markets_summary({"market": self.market})
            else:
                # Use REST API
                summary = await self._make_request("GET", f"/markets/summary?market={self.market}")

            if not summary:
                return None

            # Find market
            results = summary.get('results', []) if isinstance(summary, dict) else summary

            for market_data in results:
                if market_data.get('symbol') == self.market:
                    # Use correct keys from Paradex API
                    bid = float(market_data.get('bid', 0))
                    ask = float(market_data.get('ask', 0))
                    last_traded_price = float(market_data.get('last_traded_price', 0))
                    mark_price = float(market_data.get('mark_price', 0))

                    # Prefer mid price from bid/ask
                    if bid > 0 and ask > 0:
                        return (bid + ask) / 2
                    # Fall back to mark price or last traded price
                    return mark_price or last_traded_price or None

            return None

        except Exception as e:
            print(f"❌ Paradex error: {e}")
            return None

    async def get_bid_ask(self) -> Optional[tuple]:
        """
        Get current bid and ask prices

        Returns:
            Tuple of (bid, ask) or None if error
        """
        try:
            # Try SDK first
            if self.client:
                summary = self.client.api_client.fetch_markets_summary({"market": self.market})
            else:
                # Use REST API
                summary = await self._make_request("GET", f"/markets/summary?market={self.market}")

            if not summary:
                return None

            # Find market
            results = summary.get('results', []) if isinstance(summary, dict) else summary

            for market_data in results:
                # Handle both dict and object responses
                symbol = market_data.get('symbol') if isinstance(market_data, dict) else getattr(market_data, 'symbol', None)

                if symbol == self.market:
                    # Extract bid/ask from dict or object
                    if isinstance(market_data, dict):
                        bid = float(market_data.get('bid', 0) or 0)
                        ask = float(market_data.get('ask', 0) or 0)
                    else:
                        bid = float(getattr(market_data, 'bid', 0) or 0)
                        ask = float(getattr(market_data, 'ask', 0) or 0)

                    if bid > 0 and ask > 0:
                        return (bid, ask)

            return None

        except Exception as e:
            print(f"❌ Paradex bid/ask error: {e}")
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
            # Get market data to fetch bid/ask prices
            if self.client:
                summary = self.client.api_client.fetch_markets_summary({"market": self.market})
            else:
                summary = await self._make_request("GET", f"/markets/summary?market={self.market}")

            if not summary:
                raise ValueError("Could not fetch market data")

            # Find market and extract bid/ask
            results = summary.get('results', []) if isinstance(summary, dict) else summary
            bid = None
            ask = None

            for market_data in results:
                if market_data.get('symbol') == self.market:
                    bid = float(market_data.get('bid', 0))
                    ask = float(market_data.get('ask', 0))
                    break

            if not bid or not ask:
                raise ValueError("Could not fetch bid/ask prices")

            # Use bid/ask directly to avoid slippage issues
            # BUY: use ask price (best offer)
            # SELL: use bid price (best bid)
            if side.upper() == 'BUY':
                limit_price = ask
            else:
                limit_price = bid

            print(f"ℹ️  Using orderbook price: BID=${bid:.4f} ASK=${ask:.4f}")
            print(f"   Order: {side} at ${limit_price:.4f}")

            # Round to 0.0001 (tick size for Paradex)
            limit_price = round(limit_price, 4)

            # Try SDK first
            if self.client and PARADEX_SDK_AVAILABLE:
                # Ensure size is an integer (Paradex requires whole units)
                size_int = int(size)

                # Use SDK Order object with MARKET type
                order = Order(
                    market=self.market,
                    order_type=OrderType.Market,
                    order_side=OrderSide.Buy if side.upper() == 'BUY' else OrderSide.Sell,
                    size=Decimal(str(size_int))
                )
                # Submit market order
                result = self.client.api_client.submit_order(order=order)

                # Debug: Print full response
                print(f"🔍 [DEBUG] Paradex submit_order response: {result}")

            else:
                # Ensure size is an integer (Paradex requires whole units)
                size_int = int(size)

                # Use REST API with MARKET type
                order_params = {
                    'market': self.market,
                    'side': side.upper(),
                    'type': 'MARKET',
                    'size': str(size_int)
                }
                result = await self._make_request("POST", "/orders", order_params, signed=True)

                # Debug: Print full response
                print(f"🔍 [DEBUG] Paradex REST API response: {result}")

            if result:
                # Use the integer size for display
                display_size = int(size)
                print(f"✓ Paradex order placed: {side} {display_size} {self.market}")
                print(f"  Order ID: {result.get('id', 'N/A') if isinstance(result, dict) else getattr(result, 'id', 'N/A')}")
                print(f"  Price: {limit_price:.2f}")

                # Check order status if available
                if isinstance(result, dict):
                    status = result.get('status', 'UNKNOWN')
                    print(f"  Status: {status}")
                elif hasattr(result, 'status'):
                    print(f"  Status: {result.status}")

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
            if self.client:
                return self.client.api_client.fetch_order(order_id)
            else:
                return await self._make_request("GET", f"/orders/{order_id}", signed=True)
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
            if self.client:
                return self.client.api_client.fetch_account_summary()
            else:
                return await self._make_request("GET", "/account", signed=True)
        except Exception as e:
            print(f"❌ Paradex balance error: {e}")
            return None

    async def get_funding_rate(self) -> Optional[Dict[str, Any]]:
        """
        Get current funding rate for the market

        Paradex uses continuous funding (pro-rated by holding time) with ±5% annual cap

        Returns:
            Dict with funding rate data:
            {
                'funding_rate': float,  # 8-hour funding rate (e.g., 0.0001 = 0.01%)
                'funding_rate_pct': float,  # As percentage (e.g., 0.01)
                'funding_rate_annual': float,  # Annualized rate
                'next_funding_time': int,  # Unix timestamp
                'market': str
            }
            or None if error
        """
        try:
            # Try SDK first if available
            if self.client:
                try:
                    # Use markets_summary for live data (not fetch_markets which returns config)
                    markets = self.client.api_client.fetch_markets_summary({"market": self.market})

                    # Validate response type
                    if markets and isinstance(markets, (list, dict)):
                        # Handle dict response with results array
                        if isinstance(markets, dict) and 'results' in markets:
                            markets = markets['results']

                        # Ensure we have a list
                        if not isinstance(markets, list):
                            markets = [markets]

                        # Find our market
                        for market in markets:
                            # Skip non-dict items
                            if not isinstance(market, dict):
                                continue

                            market_symbol = market.get('symbol') or market.get('market')

                            if market_symbol == self.market:
                                funding_rate = float(market.get('funding_rate', 0))

                                # Paradex uses 8-hour funding periods (3 times per day)
                                return {
                                    'funding_rate': funding_rate,
                                    'funding_rate_pct': funding_rate * 100,
                                    'funding_rate_annual': funding_rate * 3 * 365 * 100,  # Annualized %
                                    'next_funding_time': market.get('next_funding_time', 0),
                                    'market': self.market,
                                    'source': 'SDK'
                                }

                except Exception as sdk_error:
                    print(f"ℹ️  SDK funding rate query failed, falling back to REST API: {sdk_error}")

            # Fallback to REST API - try multiple endpoints with market parameter
            endpoints_to_try = [
                f"/markets/summary?market={self.market}",  # Most reliable with market param
                f"/markets/{self.market}",
                "/markets?market=ALL"  # Get all markets if specific query fails
            ]

            for endpoint in endpoints_to_try:
                try:
                    data = await self._make_request("GET", endpoint, signed=False)

                    if not data:
                        continue

                    # Handle different response structures
                    market_data = None

                    if isinstance(data, dict):
                        # Single market response
                        if data.get('symbol') == self.market or data.get('market') == self.market:
                            market_data = data
                        # Summary with results array
                        elif 'results' in data:
                            for market in data['results']:
                                if market.get('symbol') == self.market or market.get('market') == self.market:
                                    market_data = market
                                    break
                    elif isinstance(data, list):
                        # Array of markets
                        for market in data:
                            if market.get('symbol') == self.market or market.get('market') == self.market:
                                market_data = market
                                break

                    if market_data:
                        # Extract funding rate (field name may vary)
                        funding_rate = float(market_data.get('funding_rate',
                                            market_data.get('fundingRate',
                                            market_data.get('funding', 0))))

                        next_funding = market_data.get('next_funding_time',
                                                      market_data.get('nextFundingTime',
                                                      market_data.get('funding_timestamp', 0)))

                        return {
                            'funding_rate': funding_rate,
                            'funding_rate_pct': funding_rate * 100,
                            'funding_rate_annual': funding_rate * 3 * 365 * 100,  # Annualized %
                            'next_funding_time': next_funding,
                            'market': self.market,
                            'source': f'REST:{endpoint}'
                        }

                except Exception as e:
                    # Try next endpoint
                    continue

            print(f"⚠️  Could not find funding rate for {self.market} on Paradex")
            print(f"   Tried endpoints: {endpoints_to_try}")
            return None

        except Exception as e:
            print(f"❌ Error fetching Paradex funding rate: {e}")
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
                self.client.api_client.cancel_order(order_id)
            else:
                result = await self._make_request("DELETE", f"/orders/{order_id}", signed=True)
                if not result:
                    return False

            print(f"✓ Paradex order cancelled: {order_id}")
            return True
        except Exception as e:
            print(f"❌ Paradex cancel error: {e}")
            return False

    async def close(self):
        """Close client session"""
        # Close aiohttp session if it exists
        if self._session and not self._session.closed:
            await self._session.close()
            # Wait a bit longer for the connector to finish closing
            # This prevents "Unclosed connector" warnings
            import asyncio
            await asyncio.sleep(1.0)
        # Paradex SDK doesn't require explicit cleanup
