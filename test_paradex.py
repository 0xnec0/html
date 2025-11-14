#!/usr/bin/env python3
"""
Paradex接続テスト - 超シンプル版
目的: Paradex Mainnet API接続が安定しているか確認
"""
import os
from dotenv import load_dotenv
from paradex_py import Paradex
from paradex_py.environment import Environment

# 環境変数読み込み
load_dotenv()

def test_paradex_connection():
    """Paradex接続テスト"""
    print("="*60)
    print("🔌 Paradex Mainnet 接続テスト")
    print("="*60 + "\n")

    try:
        # 1. SDK初期化
        print("1️⃣ SDK初期化中...")
        paradex = Paradex(
            env=Environment.PROD,  # Mainnet
            l1_address=os.getenv('PARADEX_L1_ADDRESS'),
            l1_private_key=os.getenv('PARADEX_L1_PRIVATE_KEY')
        )
        print("   ✅ SDK初期化成功\n")

        # 2. アカウント情報取得
        print("2️⃣ アカウント情報取得中...")
        account = paradex.account.get_account()
        print(f"   ✅ アカウント取得成功")
        print(f"   Account ID: {account.get('id', 'N/A')}")
        print(f"   L2 Address: {account.get('l2_address', 'N/A')[:10]}...\n")

        # 3. 市場一覧取得
        print("3️⃣ 市場一覧取得中...")
        markets = paradex.markets.list_markets()
        print(f"   ✅ 市場データ取得成功")
        print(f"   利用可能市場数: {len(markets)}個\n")

        # 最初の3つの市場を表示
        print("   主要市場:")
        for i, market in enumerate(markets[:3]):
            symbol = market.get('symbol', 'N/A')
            mark_price = market.get('mark_price', 'N/A')
            print(f"     {i+1}. {symbol}: ${mark_price}")

        print("\n" + "="*60)
        print("🎉 Paradex接続テスト完了！全て成功！")
        print("="*60)

    except Exception as e:
        print(f"\n❌ エラー発生: {e}")
        print(f"エラータイプ: {type(e).__name__}")
        raise

if __name__ == "__main__":
    test_paradex_connection()
