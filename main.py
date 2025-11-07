#!/usr/bin/env python3
"""
XMR Trading Bot - Simultaneous Execution on Paradex and Lighter
Main entry point for the trading bot
"""

import asyncio
import argparse
import sys
from bot.config import Config
from bot.trading_bot import TradingBot


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='XMR Trading Bot for Paradex and Lighter DEX'
    )

    parser.add_argument(
        '--config',
        type=str,
        help='Path to configuration file'
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Price command
    price_parser = subparsers.add_parser('price', help='Get current prices from both exchanges')

    # Trade command
    trade_parser = subparsers.add_parser('trade', help='Execute simultaneous trade')
    trade_parser.add_argument('side', choices=['BUY', 'SELL'], help='Order side')
    trade_parser.add_argument('amount', type=float, help='Amount to trade')
    trade_parser.add_argument('--paradex-only', action='store_true', help='Only trade on Paradex')
    trade_parser.add_argument('--lighter-only', action='store_true', help='Only trade on Lighter')

    # Arbitrage command
    arb_parser = subparsers.add_parser('arbitrage', help='Check for arbitrage opportunities')
    arb_parser.add_argument('--execute', action='store_true', help='Execute arbitrage if found')
    arb_parser.add_argument('--amount', type=float, help='Amount to trade (required with --execute)')
    arb_parser.add_argument('--min-spread', type=float, default=0.5, help='Minimum spread percentage (default: 0.5%%)')

    # Monitor command
    monitor_parser = subparsers.add_parser('monitor', help='Monitor positions and balances')

    args = parser.parse_args()

    # Load configuration
    config = Config(config_file=args.config)

    if not config.validate():
        print("\n❌ Invalid configuration. Please check your settings.")
        print("\nYou can provide configuration via:")
        print("  1. Environment variables (PARADEX_L1_ADDRESS, LIGHTER_API_KEY, etc.)")
        print("  2. Configuration file (use --config option)")
        print("\nSee config.example.json for template")
        sys.exit(1)

    # Initialize bot
    print("="*60)
    print("XMR Trading Bot - Paradex & Lighter")
    print("="*60)

    try:
        bot = TradingBot(config)
    except Exception as e:
        print(f"\n❌ Failed to initialize bot: {e}")
        sys.exit(1)

    # Execute command
    try:
        if args.command == 'price':
            await bot.get_prices()

        elif args.command == 'trade':
            result = await bot.execute_simultaneous_trade(
                side=args.side,
                amount=args.amount,
                paradex_only=args.paradex_only,
                lighter_only=args.lighter_only
            )

            if not result['success']:
                sys.exit(1)

        elif args.command == 'arbitrage':
            if args.execute:
                if not args.amount:
                    print("❌ --amount is required when using --execute")
                    sys.exit(1)

                result = await bot.execute_arbitrage(args.amount)

                if not result['success']:
                    sys.exit(1)
            else:
                await bot.check_arbitrage_opportunity(min_spread_pct=args.min_spread)

        elif args.command == 'monitor':
            await bot.monitor_positions()

        else:
            parser.print_help()
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\n✅ Done")


if __name__ == '__main__':
    asyncio.run(main())
