#!/usr/bin/env python3
"""
Paradex成行注文テスト

目的: Paradexでの成行注文（ヘッジ用）をテスト
戦略: 最小額で成行注文を出して、即座にキャンセルまたは決済
"""
import os
import asyncio
from dotenv import load_dotenv
from paradex_py import Paradex
from paradex_py.environment import PROD

# 環境変数読み込み
load_dotenv()

async def test_paradex_market_order():
    """Paradex成行注文テスト"""
    print("="*60)
    print("🧪 Paradex 成行注文テスト")
    print("="*60)
    print()

    try:
        # 1. SDK初期化
        print("1️⃣ SDK初期化中...")
        paradex = Paradex(
            env=PROD,
            l1_address=os.getenv('PARADEX_L1_ADDRESS'),
            l1_private_key=os.getenv('PARADEX_L1_PRIVATE_KEY')
        )
        print(f"   ✅ SDK初期化成功")
        print(f"   L2 Address: {hex(paradex.account.l2_address)}\n")

        # 2. 市場情報取得
        print("2️⃣ 市場情報取得中...")
        test_market = os.getenv('TEST_MARKET', 'BTC-USD-PERP')

        markets = paradex.api_client.fetch_markets()

        # marketsの構造を確認
        if isinstance(markets, dict) and 'results' in markets:
            markets_list = markets['results']
        elif isinstance(markets, list):
            markets_list = markets
        else:
            markets_list = [markets]

        # テスト市場を検索
        market_info = None
        for market in markets_list:
            if market.get('symbol') == test_market:
                market_info = market
                break

        if not market_info:
            print(f"❌ 市場 {test_market} が見つかりません")
            return

        mark_price = float(market_info.get('mark_price', 0))
        min_order_size = float(market_info.get('min_order_size', 0))

        print(f"   ✅ 市場情報取得成功")
        print(f"   市場: {test_market}")
        print(f"   マーク価格: ${mark_price:,.2f}")
        print(f"   最小注文サイズ: {min_order_size}\n")

        # 3. アカウント残高確認
        print("3️⃣ アカウント残高確認中...")
        # TODO: 残高APIを実装
        print("   ⚠️  残高API未実装 - スキップ\n")

        # 4. 成行注文パラメータ計算
        print("4️⃣ 成行注文パラメータ計算中...")

        # 最小サイズで注文（約$20相当）
        order_size = min_order_size
        estimated_value = order_size * mark_price

        print(f"   注文サイズ: {order_size}")
        print(f"   推定金額: ${estimated_value:.2f}")
        print()

        # 5. 成行注文作成
        print("5️⃣ 成行注文を作成中...")
        print("   ⚠️  実際の注文は後で実装します")
        print("   （まずはParadex SDK APIを確認）\n")

        # paradex SDKのメソッドを確認
        print("📋 Paradex SDKで利用可能なメソッド:")
        # api_clientのメソッドを確認
        api_methods = [method for method in dir(paradex.api_client) if not method.startswith('_')]
        print(f"   API Client メソッド数: {len(api_methods)}")

        # 注文関連のメソッドを探す
        order_methods = [m for m in api_methods if 'order' in m.lower()]
        print(f"   注文関連メソッド: {order_methods}\n")

        print("="*60)
        print("🎉 テスト完了！")
        print("="*60)
        print()
        print("📝 次のステップ:")
        print("   1. Paradex SDKの注文APIドキュメントを確認")
        print("   2. 成行注文メソッドを実装")
        print("   3. 最小額でテスト実行")
        print()

    except Exception as e:
        print(f"\n❌ エラー発生: {e}")
        print(f"エラータイプ: {type(e).__name__}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_paradex_market_order())
