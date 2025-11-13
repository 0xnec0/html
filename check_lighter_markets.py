#!/usr/bin/env python3
"""
Lighterで利用可能なマーケットを確認するスクリプト
Check available markets on Lighter DEX
"""

import asyncio
import aiohttp
import json
from bot.config import Config


async def check_lighter_markets():
    """Check available markets on Lighter"""
    config = Config()

    base_url = "https://mainnet.zklighter.elliot.ai"
    proxy_url = config.proxy_url

    print("="*60)
    print("Lighter DEX - 利用可能なマーケット一覧")
    print("="*60)
    print(f"API: {base_url}")
    if proxy_url:
        print(f"Proxy: 使用中")
    print()

    try:
        async with aiohttp.ClientSession() as session:
            # Try without market parameter to get all markets
            url = f"{base_url}/api/v1/orderBookDetails"

            print(f"📡 APIリクエスト中...")
            async with session.get(url, proxy=proxy_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    data = await response.json()

                    if isinstance(data, dict) and 'order_book_details' in data:
                        books = data['order_book_details']

                        print(f"\n✅ {len(books)} 個のマーケットが見つかりました:\n")

                        # Sort by symbol
                        books_sorted = sorted(books, key=lambda x: x.get('symbol', ''))

                        for book in books_sorted:
                            symbol = book.get('symbol', 'UNKNOWN')
                            market_id = book.get('market_id', 'N/A')
                            asks = book.get('asks', [])
                            bids = book.get('bids', [])
                            price_decimals = book.get('price_decimals', 0)
                            size_decimals = book.get('size_decimals', 0)
                            last_price = book.get('last_trade_price', 0)

                            # Check if market has liquidity
                            has_liquidity = len(asks) > 0 and len(bids) > 0
                            liquidity_status = "✅ アクティブ" if has_liquidity else "⚠️  流動性なし"

                            print(f"  {symbol:8} (ID: {market_id:3}) {liquidity_status}")
                            print(f"           最終価格: ${float(last_price):>10.4f}")
                            print(f"           注文数: Bids={len(bids):>3}, Asks={len(asks):>3}")
                            print(f"           精度: Price={price_decimals}, Size={size_decimals}")
                            print()

                        # Show summary
                        active_markets = [b for b in books if len(b.get('asks', [])) > 0 and len(b.get('bids', [])) > 0]
                        print("="*60)
                        print(f"📊 サマリー:")
                        print(f"   全マーケット数: {len(books)}")
                        print(f"   アクティブマーケット: {len(active_markets)}")
                        print(f"   流動性なし: {len(books) - len(active_markets)}")
                        print()

                        # Check if ENA exists
                        ena_market = next((b for b in books if b.get('symbol', '').upper() == 'ENA'), None)
                        if ena_market:
                            print("🔍 ENAマーケットの状態:")
                            print(f"   存在: はい")
                            print(f"   Market ID: {ena_market.get('market_id')}")
                            print(f"   注文数: Bids={len(ena_market.get('bids', []))}, Asks={len(ena_market.get('asks', []))}")
                            if len(ena_market.get('bids', [])) == 0 and len(ena_market.get('asks', [])) == 0:
                                print("   ⚠️  オーダーブックが空です！")
                                print("   → このマーケットは現在使用できません")
                        else:
                            print("🔍 ENAマーケット: 見つかりませんでした")

                        print()
                        print("💡 推奨マーケット (流動性あり):")
                        for market in active_markets[:5]:  # Show top 5
                            print(f"   - {market.get('symbol')}")

                    else:
                        print("❌ 予期しないレスポンス形式")
                        print(json.dumps(data, indent=2)[:500])

                else:
                    print(f"❌ APIエラー: HTTP {response.status}")
                    text = await response.text()
                    print(f"   {text[:200]}")

    except asyncio.TimeoutError:
        print("❌ タイムアウト: APIへの接続がタイムアウトしました")
        print("   → プロキシ設定を確認してください")
    except aiohttp.ClientError as e:
        print(f"❌ 接続エラー: {e}")
        print("   → ネットワーク接続を確認してください")
    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()

    print("="*60)


if __name__ == '__main__':
    asyncio.run(check_lighter_markets())
