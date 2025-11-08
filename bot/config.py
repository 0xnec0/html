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
    def lighter_api_key(self) -> str:
        """Lighter API key"""
        return os.getenv('LIGHTER_API_KEY', self.config_data.get('lighter', {}).get('api_key', ''))

    @property
    def lighter_api_secret(self) -> str:
        """Lighter API secret"""
        return os.getenv('LIGHTER_API_SECRET', self.config_data.get('lighter', {}).get('api_secret', ''))

    @property
    def lighter_private_key(self) -> str:
        """Lighter private key for signing transactions"""
        return os.getenv('LIGHTER_PRIVATE_KEY', self.config_data.get('lighter', {}).get('private_key', ''))

    @property
    def lighter_market(self) -> str:
        """Lighter market symbol"""
        return os.getenv('LIGHTER_MARKET', self.config_data.get('lighter', {}).get('market', 'DOGE'))

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

    def validate(self) -> bool:
        """
        Validate required configuration

        Returns:
            True if configuration is valid, False otherwise
        """
        missing = []

        # Check Paradex: L1 OR L2 credentials required
        has_l1 = self.paradex_l1_address and self.paradex_l1_private_key
        has_l2 = self.paradex_l2_address and self.paradex_l2_private_key

        if not (has_l1 or has_l2):
            missing.append('Paradex credentials (L1 Address+Key OR L2 Address+Key)')
        elif has_l2 and not has_l1:
            # L2-only mode - warn about SDK requirement
            print("ℹ️  L2-only authentication detected")
            print("   Note: Paradex SDK required for L2-only mode")
            print("   Install with: pip install paradex-py")

        # Check Lighter credentials
        if not self.lighter_api_key:
            missing.append('Lighter API Key')
        if not self.lighter_api_secret:
            missing.append('Lighter API Secret')

        if missing:
            print(f"❌ Missing required configuration: {', '.join(missing)}")
            return False

        return True
