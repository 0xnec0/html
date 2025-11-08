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
                 l2_address: str = None, l2_private_key: str = None):
        """
        Initialize Paradex client

        Args:
            env: Environment (TESTNET or MAINNET)
            l1_address: Ethereum L1 address
            l1_private_key: Ethereum L1 private key
            market: Trading market symbol
            l2_address: Optional L2 address (for existing accounts)
            l2_private_key: Optional L2 private key (for existing accounts)
        """
        self.market = market
        self.l1_address = l1_address
        self.l1_private_key = l1_private_key
        self.l2_address = l2_address
        self.l2_private_key = l2_private_key
        self.env_name = env.upper()

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
            async with aiohttp.ClientSession() as session:
                if method == "GET":
                    async with session.get(url, headers=headers) as response:
                        if response.status == 200:
                            return await response.json()
                        else:
                            error_text = await response.text()
                            print(f"❌ Paradex API error: {response.status} - {error_text}")
                            return None
                elif method == "POST":
                    async with session.post(url, json=data, headers=headers) as response:
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
            slippage_multiplier = 1.01 if side.upper() == 'BUY' else 0.99
            limit_price = current_price * slippage_multiplier

            # Try SDK first
            if self.client and PARADEX_SDK_AVAILABLE:
                # Use SDK Order object
                order = Order(
                    market=self.market,
                    order_type=OrderType.Limit,
                    order_side=OrderSide.Buy if side.upper() == 'BUY' else OrderSide.Sell,
                    size=Decimal(str(size)),
                    limit_price=Decimal(str(limit_price)),
                    instruction="IOC"  # Immediate or Cancel
                )
                result = self.client.api_client.submit_order(order=order)
            else:
                # Use REST API
                order_params = {
                    'market': self.market,
                    'side': side.upper(),
                    'type': 'LIMIT',
                    'size': str(size),
                    'limit_price': str(limit_price),
                    'time_in_force': 'IOC',  # Immediate or Cancel
                }
                result = await self._make_request("POST", "/orders", order_params, signed=True)

            if result:
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
