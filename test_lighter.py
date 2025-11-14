#!/usr/bin/env python3
"""
Lighter接続テスト - REST API版
目的: Lighter Mainnet REST API接続が安定しているか確認
"""
import os
import asyncio
import aiohttp
from dotenv import load_dotenv

# 環境変数読み込み
load_dotenv()

async def test_lighter_connection():
    """Lighter REST API接続テスト"""
    print("="*60)
    print("🔌 Lighter Mainnet 接続テスト (REST API)")
    print("="*60 + "\n")

    base_url = os.getenv('LIGHTER_BASE_URL', 'https://mainnet.zklighter.elliot.ai')

    async with aiohttp.ClientSession() as session:
        try:
            # 1. サーバー接続確認
            print("1️⃣ サーバー接続確認中...")
            print(f"   Base URL: {base_url}\n")

            # 2. 市場情報取得（公開エンドポイント）
            print("2️⃣ 市場情報取得中...")

            # Lighter API正式エンドポイント
            markets_url = f"{base_url}/api/v1/orderBooks"

            async with session.get(markets_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    markets = await response.json()
                    print(f"   ✅ 市場データ取得成功")

                    # レスポンスがリストかdictか確認
                    if isinstance(markets, dict) and 'data' in markets:
                        markets_list = markets['data']
                    elif isinstance(markets, list):
                        markets_list = markets
                    else:
                        markets_list = []

                    print(f"   利用可能市場数: {len(markets_list)}個\n")

                    # 最初の3つの市場を表示
                    print("   主要市場:")
                    for i, market in enumerate(markets_list[:3]):
                        # orderBook IDとシンボル情報を表示
                        order_book_id = market.get('order_book_id', market.get('id', i))
                        symbol = market.get('symbol', f"OrderBook-{order_book_id}")
                        print(f"     {i+1}. {symbol} (ID: {order_book_id})")
                else:
                    print(f"   ⚠️  HTTP {response.status}: {await response.text()}")

            # 3. ステータスチェック
            print(f"\n3️⃣ APIステータスチェック...")

            # Lighterのステータスエンドポイント
            status_url = f"{base_url}/"

            try:
                async with session.get(status_url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        status_data = await response.json()
                        print(f"   ✅ ステータス取得成功")
                        print(f"   データ: {status_data}")
                    else:
                        print(f"   ⚠️  ステータス確認: HTTP {response.status}")
            except Exception as e:
                print(f"   ℹ️  ステータスエンドポイント利用不可（問題なし）")

            print("\n" + "="*60)
            print("🎉 Lighter REST API 接続テスト完了！")
            print("="*60)

            print("\n📝 次のステップ:")
            print("   1. .env ファイルにLIGHTER_PRIVATE_KEYを設定")
            print("   2. 認証が必要なエンドポイント（アカウント情報など）をテスト")

        except aiohttp.ClientError as e:
            print(f"\n❌ ネットワークエラー: {e}")
            print(f"エラータイプ: {type(e).__name__}")
            raise
        except Exception as e:
            print(f"\n❌ エラー発生: {e}")
            print(f"エラータイプ: {type(e).__name__}")
            import traceback
            traceback.print_exc()
            raise

if __name__ == "__main__":
    asyncio.run(test_lighter_connection())
