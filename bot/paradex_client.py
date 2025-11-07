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
    from paradex_py.environment import Environment
    PARADEX_SDK_AVAILABLE = True
except ImportError:
    PARADEX_SDK_AVAILABLE = False
    print("⚠ Paradex SDK not available, using REST API")


class ParadexClient:
    """Client for interacting with Paradex DEX"""

    def __init__(self, env: str, l1_address: str, l1_private_key: str, market: str = "DOGE-USD-PERP"):
        """
        Initialize Paradex client

        Args:
            env: Environment (TESTNET or MAINNET)
            l1_address: Ethereum L1 address
            l1_private_key: Ethereum L1 private key
            market: Trading market symbol
        """
        self.market = market
        self.l1_address = l1_address
        self.l1_private_key = l1_private_key
        self.env_name = env.upper()

        # Set API base URL
        if self.env_name == "TESTNET":
            self.base_url = "https://api.testnet.paradex.trade/v1"
        else:
            self.base_url = "https://api.prod.paradex.trade/v1"

        # Initialize account
        self.account = Account.from_key(l1_private_key)

        # Try SDK initialization if available
        self.client = None
        if PARADEX_SDK_AVAILABLE:
            try:
                env_obj = Environment.TESTNET if self.env_name == "TESTNET" else Environment.PROD
                self.client = Paradex(
                    env=env_obj,
                    l1_address=l1_address,
                    l1_private_key=l1_private_key
                )
                print(f"✓ Paradex initialized with SDK")
                print(f"  L2 Address: {hex(self.client.account.l2_address)}")
            except Exception as e:
                print(f"⚠ SDK init failed, using REST API: {e}")
                self.client = None
        else:
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
                summary = self.client.api_client.fetch_markets_summary()
            else:
                # Use REST API
                summary = await self._make_request("GET", "/markets/summary")

            if not summary:
                return None

            # Find market
            results = summary.get('results', []) if isinstance(summary, dict) else summary
            for market_data in results:
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
            slippage_multiplier = 1.01 if side.upper() == 'BUY' else 0.99
            limit_price = current_price * slippage_multiplier

            order_params = {
                'market': self.market,
                'side': side.upper(),
                'type': 'LIMIT',
                'size': str(size),
                'limit_price': str(limit_price),
                'time_in_force': 'IOC',  # Immediate or Cancel
            }

            # Try SDK first
            if self.client:
                result = self.client.api_client.create_order(**order_params)
            else:
                # Use REST API
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
                return self.client.api_client.fetch_account()
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
