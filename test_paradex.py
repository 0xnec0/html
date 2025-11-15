#!/usr/bin/env python3
"""
Paradex接続テスト - 超シンプル版
目的: Paradex Mainnet API接続が安定しているか確認
"""
import os
from dotenv import load_dotenv
from paradex_client import create_paradex_client

# 環境変数読み込み
load_dotenv()

def test_paradex_connection():
    """Paradex接続テスト"""
    print("="*60)
    print("🔌 Paradex Mainnet 接続テスト")
    print("="*60 + "\n")

    try:
        # 1. SDK初期化（プロキシサポート付き）
        print("1️⃣ SDK初期化中...")
        paradex = create_paradex_client()
        print("   ✅ SDK初期化成功\n")

        # 2. アカウント情報表示
        print("2️⃣ アカウント情報表示...")
        # paradex.accountは直接プロパティとしてアクセス
        print(f"   ✅ アカウント情報:")
        print(f"   L2 Address: {hex(paradex.account.l2_address)}")
        print(f"   L2 Public Key: {hex(paradex.account.l2_public_key)[:20]}...\n")

        # 3. 市場一覧取得
        print("3️⃣ 市場一覧取得中...")
        markets = paradex.api_client.fetch_markets()
        print(f"   ✅ 市場データ取得成功")

        # marketsがリストかdictか確認して処理
        if isinstance(markets, dict) and 'results' in markets:
            markets_list = markets['results']
        elif isinstance(markets, list):
            markets_list = markets
        else:
            markets_list = [markets]

        print(f"   利用可能市場数: {len(markets_list)}個\n")

        # 最初の3つの市場を表示
        print("   主要市場:")
        for i, market in enumerate(markets_list[:3]):
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
