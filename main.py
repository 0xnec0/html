#!/usr/bin/env python3
"""
Multi-DEX Trading Bot - Simultaneous Execution on Paradex and Lighter
Main entry point for the trading bot
"""

import asyncio
import argparse
import sys
from bot.config import Config
from bot.trading_bot import TradingBot
from bot.auto_trader import AutoTrader
from bot.delta_neutral_strategy import DeltaNeutralStrategy


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='Multi-DEX Trading Bot for Paradex and Lighter'
    )

    parser.add_argument(
        '--config',
        type=str,
        help='Path to configuration file'
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Test command
    test_parser = subparsers.add_parser('test', help='Test connections to both exchanges')

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

    # Auto loop command
    autoloop_parser = subparsers.add_parser('autoloop', help='Run automated trading loop with random hold times')
    autoloop_parser.add_argument('side', choices=['BUY', 'SELL'], help='Initial order side')
    autoloop_parser.add_argument('amount', type=float, help='Amount to trade')
    autoloop_parser.add_argument('--min-hours', type=float, default=2.0, help='Minimum hold time in hours (default: 2.0)')
    autoloop_parser.add_argument('--max-hours', type=float, default=3.0, help='Maximum hold time in hours (default: 3.0)')
    autoloop_parser.add_argument('--max-iterations', type=int, help='Maximum iterations (default: unlimited)')
    autoloop_parser.add_argument('--paradex-only', action='store_true', help='Only trade on Paradex')
    autoloop_parser.add_argument('--lighter-only', action='store_true', help='Only trade on Lighter')

    # Delta Neutral command
    delta_parser = subparsers.add_parser('delta-neutral', help='Run delta neutral strategy (Paradex LONG + Lighter SHORT)')
    delta_parser.add_argument('--leverage', type=int, default=10, help='Leverage multiplier (default: 10x)')
    delta_parser.add_argument('--capital-pct', type=float, default=0.5, help='Percentage of capital to use (default: 0.5 = 50%%)')
    delta_parser.add_argument('--usd-amount', type=float, help='Fixed USD amount per position (e.g., 50 for $50)')
    delta_parser.add_argument('--min-hours', type=float, default=2.0, help='Minimum hold time in hours (default: 2.0)')
    delta_parser.add_argument('--max-hours', type=float, default=3.0, help='Maximum hold time in hours (default: 3.0)')
    delta_parser.add_argument('--max-cycles', type=int, help='Maximum cycles (default: unlimited)')

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
    print("Multi-DEX Trading Bot - Paradex & Lighter")
    print("="*60)

    try:
        bot = TradingBot(config)
    except Exception as e:
        print(f"\n❌ Failed to initialize bot: {e}")
        sys.exit(1)

    # Execute command
    try:
        if args.command == 'test':
            result = await bot.test_connections()

            # Exit with error if any connection failed
            if not (result['paradex']['connected'] and result['lighter']['connected']):
                sys.exit(1)

        elif args.command == 'price':
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

        elif args.command == 'autoloop':
            auto_trader = AutoTrader(bot)
            await auto_trader.run_loop(
                side=args.side,
                amount=args.amount,
                min_hold_hours=args.min_hours,
                max_hold_hours=args.max_hours,
                max_iterations=args.max_iterations,
                paradex_only=args.paradex_only,
                lighter_only=args.lighter_only
            )

        elif args.command == 'delta-neutral':
            strategy = DeltaNeutralStrategy(
                bot=bot,
                leverage=args.leverage,
                capital_percentage=args.capital_pct,
                usd_amount=args.usd_amount
            )
            await strategy.run_loop(
                hold_time_hours=(args.min_hours, args.max_hours),
                max_cycles=args.max_cycles
            )

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
