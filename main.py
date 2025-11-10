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
    delta_parser.add_argument('--once', action='store_true', help='Run only once (default: loop continuously)')
    delta_parser.add_argument('--max-cycles', type=int, help='Maximum cycles in loop mode (default: unlimited)')

    # Close All command
    close_parser = subparsers.add_parser('close-all', help='Close all open positions (emergency stop)')
    close_parser.add_argument('--size', type=float, help='Position size to close (optional - auto-detected if not specified)')
    close_parser.add_argument('--paradex-only', action='store_true', help='Close Paradex positions only')
    close_parser.add_argument('--lighter-only', action='store_true', help='Close Lighter positions only')

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
            # Use command-line args if provided, otherwise use config
            usd_amount = args.usd_amount if args.usd_amount is not None else config.delta_neutral_usd_amount
            leverage = args.leverage if args.leverage != 10 else config.delta_neutral_leverage
            capital_pct = args.capital_pct if args.capital_pct != 0.5 else config.delta_neutral_capital_pct
            min_hours = args.min_hours if args.min_hours != 2.0 else config.delta_neutral_min_hours
            max_hours = args.max_hours if args.max_hours != 3.0 else config.delta_neutral_max_hours

            strategy = DeltaNeutralStrategy(
                bot=bot,
                leverage=leverage,
                capital_percentage=capital_pct,
                usd_amount=usd_amount
            )

            if args.once:
                # Run once: open -> wait -> close
                import random
                from datetime import datetime, timedelta

                try:
                    # Open position
                    open_result = await strategy.open_delta_neutral_position()

                    if not open_result['success']:
                        print("❌ Failed to open position")
                        sys.exit(1)

                    # Calculate hold time
                    hold_seconds = random.uniform(min_hours * 3600, max_hours * 3600)
                    hold_minutes = hold_seconds / 60
                    close_time = datetime.now() + timedelta(seconds=hold_seconds)

                    print(f"\n⏰ Position will close at: {close_time.strftime('%Y-%m-%d %H:%M:%S')}")
                    print(f"   (holding for {hold_minutes:.1f} minutes)")

                    # Wait
                    await asyncio.sleep(hold_seconds)

                    # Close position
                    close_result = await strategy.close_delta_neutral_position()

                    if not close_result['success']:
                        print("❌ Failed to close position")
                        sys.exit(1)

                except (KeyboardInterrupt, asyncio.CancelledError):
                    print("\n\n⚠️  Interrupted by user")
                    if strategy.position_open:
                        print("🔄 Closing open position...")
                        await strategy.close_delta_neutral_position()
                    raise KeyboardInterrupt
            else:
                # Run in loop mode (default)
                try:
                    await strategy.run_loop(
                        hold_time_hours=(min_hours, max_hours),
                        max_cycles=args.max_cycles
                    )
                except (KeyboardInterrupt, asyncio.CancelledError):
                    # run_loop already handles position closing
                    # Just re-raise to reach outer exception handler
                    raise

        elif args.command == 'close-all':
            # Try to auto-detect position size if not specified
            position_size = args.size

            if not position_size:
                # Try to load from saved position file
                saved_position = DeltaNeutralStrategy.load_current_position()
                if saved_position and 'size' in saved_position:
                    position_size = saved_position['size']
                    print(f"ℹ️  Auto-detected position size from saved data: {position_size}")
                else:
                    print("❌ No position size specified and no saved position found")
                    print("   Either:")
                    print("   1. Specify size manually: python main.py close-all --size 156")
                    print("   2. Or make sure delta-neutral strategy has saved position data")
                    sys.exit(1)

            print("\n" + "="*60)
            print("🛑 EMERGENCY STOP - Closing All Positions")
            print("="*60)
            print(f"   Position size: {position_size}")

            # Get current prices for reference
            paradex_price, lighter_price = await bot.get_prices()

            print(f"\n📊 Current prices:")
            if paradex_price:
                print(f"   Paradex: ${paradex_price:.4f}")
            if lighter_price:
                print(f"   Lighter: ${lighter_price:.4f}")

            # Close positions
            tasks = []

            if not args.lighter_only:
                print(f"\n🔄 Closing Paradex position (SELL {position_size})...")
                tasks.append(bot.paradex.place_market_order('SELL', position_size))

            if not args.paradex_only:
                print(f"🔄 Closing Lighter position (BUY {position_size})...")
                tasks.append(bot.lighter.place_market_order('BUY', position_size))

            # Execute closures
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Check results
                success_count = 0
                for i, result in enumerate(results):
                    if not isinstance(result, Exception) and result:
                        success_count += 1

                print(f"\n✅ Closed {success_count}/{len(tasks)} positions successfully")

                if success_count < len(tasks):
                    print("⚠️  Some positions failed to close - check manually!")
                    sys.exit(1)
            else:
                print("⚠️  No positions to close")

        else:
            parser.print_help()
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        # Don't exit here - let finally block run
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up client sessions
        if 'bot' in locals():
            try:
                await bot.close()
                print("✓ Sessions closed")
            except Exception as e:
                print(f"⚠️  Error closing sessions: {e}")

    print("\n✅ Done")


if __name__ == '__main__':
    asyncio.run(main())
