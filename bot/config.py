"""
Configuration management for the trading bot
"""

import os
import json
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Configuration class for trading bot"""

    def __init__(self, config_file: str = None):
        """
        Initialize configuration

        Args:
            config_file: Path to JSON configuration file (optional)
        """
        self.config_data = {}

        if config_file and os.path.exists(config_file):
            with open(config_file, 'r') as f:
                self.config_data = json.load(f)

    # Paradex Configuration
    @property
    def paradex_env(self) -> str:
        """Paradex environment (TESTNET or MAINNET)"""
        return os.getenv('PARADEX_ENV', self.config_data.get('paradex', {}).get('env', 'TESTNET'))

    @property
    def paradex_l1_address(self) -> str:
        """Paradex L1 Ethereum address"""
        return os.getenv('PARADEX_L1_ADDRESS', self.config_data.get('paradex', {}).get('l1_address', ''))

    @property
    def paradex_l1_private_key(self) -> str:
        """Paradex L1 private key"""
        return os.getenv('PARADEX_L1_PRIVATE_KEY', self.config_data.get('paradex', {}).get('l1_private_key', ''))

    @property
    def paradex_l2_address(self) -> str:
        """Paradex L2 address (for existing accounts)"""
        return os.getenv('PARADEX_L2_ADDRESS', self.config_data.get('paradex', {}).get('l2_address', ''))

    @property
    def paradex_l2_private_key(self) -> str:
        """Paradex L2 private key (for existing accounts)"""
        return os.getenv('PARADEX_L2_PRIVATE_KEY', self.config_data.get('paradex', {}).get('l2_private_key', ''))

    @property
    def paradex_market(self) -> str:
        """Paradex market symbol"""
        return os.getenv('PARADEX_MARKET', self.config_data.get('paradex', {}).get('market', 'DOGE-USD-PERP'))

    # Lighter Configuration
    @property
    def lighter_private_key(self) -> str:
        """Lighter API key private key for signing transactions"""
        return os.getenv('LIGHTER_PRIVATE_KEY', self.config_data.get('lighter', {}).get('private_key', ''))

    @property
    def lighter_account_index(self) -> int:
        """Lighter account index"""
        index = os.getenv('LIGHTER_ACCOUNT_INDEX', self.config_data.get('lighter', {}).get('account_index', '0'))
        return int(index)

    @property
    def lighter_api_key_index(self) -> int:
        """Lighter API key index (2-254)"""
        index = os.getenv('LIGHTER_API_KEY_INDEX', self.config_data.get('lighter', {}).get('api_key_index', '2'))
        return int(index)

    @property
    def lighter_market(self) -> str:
        """Lighter market symbol"""
        return os.getenv('LIGHTER_MARKET', self.config_data.get('lighter', {}).get('market', 'DOGE'))

    # Proxy Configuration
    @property
    def use_proxy(self) -> bool:
        """Whether to use proxy"""
        use = os.getenv('USE_PROXY', self.config_data.get('proxy', {}).get('use_proxy', 'false'))
        return use.lower() in ('true', '1', 'yes')

    @property
    def proxy_server(self) -> str:
        """Proxy server address"""
        return os.getenv('PROXY_SERVER', self.config_data.get('proxy', {}).get('server', ''))

    @property
    def proxy_port(self) -> int:
        """Proxy port"""
        port = os.getenv('PROXY_PORT', self.config_data.get('proxy', {}).get('port', '0'))
        return int(port)

    @property
    def proxy_username(self) -> str:
        """Proxy username"""
        return os.getenv('PROXY_USERNAME', self.config_data.get('proxy', {}).get('username', ''))

    @property
    def proxy_password(self) -> str:
        """Proxy password"""
        return os.getenv('PROXY_PASSWORD', self.config_data.get('proxy', {}).get('password', ''))

    @property
    def proxy_url(self) -> str:
        """Get full proxy URL with authentication"""
        if not self.use_proxy or not self.proxy_server:
            return None

        if self.proxy_username and self.proxy_password:
            return f"http://{self.proxy_username}:{self.proxy_password}@{self.proxy_server}:{self.proxy_port}"
        else:
            return f"http://{self.proxy_server}:{self.proxy_port}"

    # Trading Configuration
    @property
    def trade_amount(self) -> float:
        """Amount to trade"""
        amount = os.getenv('TRADE_AMOUNT', self.config_data.get('trading', {}).get('amount', '0.1'))
        return float(amount)

    @property
    def slippage_tolerance(self) -> float:
        """Slippage tolerance percentage"""
        slippage = os.getenv('SLIPPAGE_TOLERANCE', self.config_data.get('trading', {}).get('slippage_tolerance', '0.5'))
        return float(slippage)

    @property
    def execution_timeout(self) -> int:
        """Timeout for order execution in seconds"""
        timeout = os.getenv('EXECUTION_TIMEOUT', self.config_data.get('trading', {}).get('execution_timeout', '30'))
        return int(timeout)

    # Delta Neutral Strategy Configuration
    @property
    def delta_neutral_usd_amount(self) -> float:
        """Fixed USD amount per position for delta neutral strategy"""
        amount = os.getenv('DELTA_NEUTRAL_USD_AMOUNT', self.config_data.get('delta_neutral', {}).get('usd_amount', '0'))
        return float(amount) if amount else None

    @property
    def delta_neutral_leverage(self) -> int:
        """Leverage multiplier for delta neutral strategy"""
        leverage = os.getenv('DELTA_NEUTRAL_LEVERAGE', self.config_data.get('delta_neutral', {}).get('leverage', '10'))
        return int(leverage)

    @property
    def delta_neutral_capital_pct(self) -> float:
        """Percentage of capital to use for delta neutral strategy"""
        pct = os.getenv('DELTA_NEUTRAL_CAPITAL_PCT', self.config_data.get('delta_neutral', {}).get('capital_pct', '0.5'))
        return float(pct)

    @property
    def delta_neutral_min_hours(self) -> float:
        """Minimum hold time in hours for delta neutral strategy"""
        hours = os.getenv('DELTA_NEUTRAL_MIN_HOURS', self.config_data.get('delta_neutral', {}).get('min_hours', '2.0'))
        return float(hours)

    @property
    def delta_neutral_max_hours(self) -> float:
        """Maximum hold time in hours for delta neutral strategy"""
        hours = os.getenv('DELTA_NEUTRAL_MAX_HOURS', self.config_data.get('delta_neutral', {}).get('max_hours', '3.0'))
        return float(hours)

    # Spread Monitoring Configuration
    @property
    def spread_max_pct(self) -> float:
        """Maximum allowed spread in percentage"""
        pct = os.getenv('SPREAD_MAX_PCT', self.config_data.get('spread', {}).get('max_pct', '0.02'))
        return float(pct)

    @property
    def spread_check_interval(self) -> float:
        """Spread check interval in seconds"""
        interval = os.getenv('SPREAD_CHECK_INTERVAL', self.config_data.get('spread', {}).get('check_interval', '2'))
        return float(interval)

    @property
    def spread_check_timeout(self) -> float:
        """Spread check timeout in seconds (0 = infinite)"""
        timeout = os.getenv('SPREAD_CHECK_TIMEOUT', self.config_data.get('spread', {}).get('check_timeout', '0'))
        return float(timeout)

    # Lighter Limit Order Configuration
    @property
    def lighter_spread_max_pct(self) -> float:
        """Maximum spread for Lighter limit orders in percentage"""
        pct = os.getenv('LIGHTER_SPREAD_MAX_PCT', self.config_data.get('lighter_order', {}).get('spread_max_pct', '0.03'))
        return float(pct)

    @property
    def lighter_order_timeout(self) -> float:
        """Timeout for Lighter limit order fill in seconds (0 = infinite)"""
        timeout = os.getenv('LIGHTER_ORDER_TIMEOUT', self.config_data.get('lighter_order', {}).get('order_timeout', '60'))
        return float(timeout)

    def validate(self) -> bool:
        """
        Validate required configuration

        Returns:
            True if configuration is valid, False otherwise
        """
        missing = []

        # Check Paradex credentials
        # L1 full auth: L1 address + L1 private key
        # L2 auth: L1 address + L2 private key (no L2 address needed)
        has_l1_full = self.paradex_l1_address and self.paradex_l1_private_key
        has_l2_auth = self.paradex_l1_address and self.paradex_l2_private_key

        if not (has_l1_full or has_l2_auth):
            missing.append('Paradex: PARADEX_L1_ADDRESS + (PARADEX_L1_PRIVATE_KEY or PARADEX_L2_PRIVATE_KEY)')
        elif has_l2_auth and not self.paradex_l1_private_key:
            # L2 auth mode - warn about SDK requirement
            print("ℹ️  L2 authentication detected (L1 address + L2 private key)")
            print("   Note: Paradex SDK required for L2 authentication")
            print("   Install with: pip install paradex-py")

        # Check Lighter credentials (optional - can work without SDK)
        # Lighter SDK is optional due to dependency conflicts
        # The bot will use REST API mode if SDK is not available
        if not self.lighter_account_index:
            print("ℹ️  Lighter account index not set - using default (0)")
            print("   Note: Get your account index from Lighter API for SDK mode")

        if missing:
            print(f"❌ Missing required configuration: {', '.join(missing)}")
            return False

        return True
