#!/usr/bin/env python3
"""
Test script to fetch Lighter market info and check decimals
"""
import asyncio
import aiohttp
import json
import sys
sys.path.insert(0, '/home/user/html')
from bot.config import Config

async def fetch_market_info():
    """Fetch market info from Lighter API"""
    config = Config()
    market = config.lighter_market
    base_url = "https://api.lighter.xyz"
    proxy_url = config.proxy_url if config.use_proxy else None

    print(f"🔍 Fetching market info for {market}...")
    print(f"   Base URL: {base_url}")
    print(f"   Proxy: {proxy_url if proxy_url else 'None'}")

    async with aiohttp.ClientSession() as session:
        url = f"{base_url}/api/v1/orderBookDetails?market={market}"

        try:
            async with session.get(url, proxy=proxy_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()

                    print(f"\n✅ Response received (status: {response.status})")
                    print(f"\n{'='*60}")
                    print("Full API Response:")
                    print(f"{'='*60}")
                    print(json.dumps(data, indent=2))

                    # Extract market info
                    if isinstance(data, dict) and 'order_book_details' in data:
                        for book in data['order_book_details']:
                            if book.get('symbol', '').upper() == market.upper():
                                print(f"\n{'='*60}")
                                print(f"Market Info for {market}:")
                                print(f"{'='*60}")
                                print(f"market_id: {book.get('market_id')}")
                                print(f"symbol: {book.get('symbol')}")
                                print(f"price_decimals: {book.get('price_decimals')}")
                                print(f"size_decimals: {book.get('size_decimals')}")
                                print(f"min_order_size: {book.get('min_order_size')}")
                                print(f"max_order_size: {book.get('max_order_size')}")
                                print(f"tick_size: {book.get('tick_size')}")
                                print(f"step_size: {book.get('step_size')}")
                                print(f"\nAll fields:")
                                for key, value in book.items():
                                    print(f"  {key}: {value}")

                                # Test size conversion
                                print(f"\n{'='*60}")
                                print("Testing Size Conversion:")
                                print(f"{'='*60}")

                                test_sizes = [1, 10, 100, 156, 1000]
                                size_decimals = book.get('size_decimals', 0)

                                for size in test_sizes:
                                    base_amount_int = int(size * (10 ** size_decimals))
                                    print(f"Size {size} → base_amount_int: {base_amount_int} (decimals: {size_decimals})")

                                return

                    print(f"\n❌ Market {market} not found in response")
                else:
                    print(f"\n❌ HTTP Error: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")

        except Exception as e:
            print(f"\n❌ Exception: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(fetch_market_info())
