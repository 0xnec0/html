#!/usr/bin/env python3
"""
Paradex成行注文テスト

目的: Paradexでの成行注文（ヘッジ用）をテスト
戦略: 最小額で成行注文を出して、すぐに確認
"""
import os
import asyncio
import time
from decimal import Decimal
from dotenv import load_dotenv
from paradex_py import Paradex
from paradex_py.common.order import Order, OrderSide, OrderType
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

        # 2. 市場情報取得（ライブ価格）
        print("2️⃣ 市場情報取得中（ライブ価格）...")
        test_market = os.getenv('TEST_PARADEX_MARKET', 'BTC-USD-PERP')

        # fetch_markets_summary() でライブ価格を取得
        markets_summary = paradex.api_client.fetch_markets_summary()

        # 市場データ検索
        market_info = None
        if isinstance(markets_summary, dict) and 'results' in markets_summary:
            for market in markets_summary['results']:
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

        if mark_price == 0 or min_order_size == 0:
            print("❌ 市場データが不正です")
            return

        # 3. アカウント残高確認
        print("3️⃣ アカウント残高確認中...")
        try:
            balances = paradex.api_client.fetch_balances()
            summary = paradex.api_client.fetch_account_summary()

            print(f"   ✅ 残高データ取得成功")
            if isinstance(summary, dict):
                equity = summary.get('equity', 0)
                print(f"   アカウント資産: ${equity}\n")
            else:
                print(f"   サマリ: {summary}\n")
        except Exception as e:
            print(f"   ⚠️  残高取得エラー: {e}\n")

        # 4. 成行注文パラメータ計算
        print("4️⃣ 成行注文パラメータ計算中...")

        # 最小サイズで注文
        order_size = Decimal(str(min_order_size))
        estimated_value = float(order_size) * mark_price

        print(f"   注文サイズ: {order_size}")
        print(f"   推定金額: ${estimated_value:.2f}\n")

        # 5. 成行注文作成＆送信
        print("5️⃣ 成行買い注文を作成・送信中...")

        # ユニークなclient_id生成
        client_id = f"test-market-buy-{int(time.time())}"

        market_order = Order(
            market=test_market,
            order_type=OrderType.Market,
            order_side=OrderSide.Buy,
            size=order_size,
            client_id=client_id
        )

        print(f"   📋 注文詳細:")
        print(f"   - Market: {test_market}")
        print(f"   - Type: Market")
        print(f"   - Side: Buy")
        print(f"   - Size: {order_size}")
        print(f"   - Client ID: {client_id}")
        print()

        print("   ⚠️  実際に注文を送信しますか？")
        print("   これは実際のお金を使います！")
        print("   続行する場合は、スクリプト内のコメントを解除してください。\n")

        # 実際の注文送信（コメントアウト - 安全のため）
        # response = paradex.api_client.submit_order(order=market_order)
        #
        # order_id = response.get('id')
        # status = response.get('status')
        #
        # print(f"   ✅ 注文送信成功！")
        # print(f"   Order ID: {order_id}")
        # print(f"   Status: {status}\n")
        #
        # # 6. 注文状態確認
        # print("6️⃣ 注文状態確認中...")
        # await asyncio.sleep(1)
        #
        # order_status = paradex.api_client.fetch_order_by_client_id(client_id=client_id)
        #
        # print(f"   Status: {order_status.get('status')}")
        # print(f"   Filled Qty: {order_status.get('filled_qty', 0)}")
        # print(f"   Avg Fill Price: ${order_status.get('avg_fill_price', 0)}\n")
        #
        # # 7. ポジション確認
        # print("7️⃣ ポジション確認中...")
        # positions = paradex.api_client.fetch_positions()
        # print(f"   Current Positions: {positions}\n")

        print("="*60)
        print("🎉 テスト完了！")
        print("="*60)
        print()
        print("📝 注文送信を有効にするには:")
        print("   1. スクリプト内の注文送信部分のコメントを解除")
        print("   2. 最小額でテスト実行")
        print("   3. 成功を確認")
        print()

    except Exception as e:
        print(f"\n❌ エラー発生: {e}")
        print(f"エラータイプ: {type(e).__name__}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_paradex_market_order())
