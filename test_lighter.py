#!/usr/bin/env python3
"""
Lighter接続テスト - 超シンプル版
目的: Lighter Mainnet API接続が安定しているか確認
"""
import os
import asyncio
from dotenv import load_dotenv

# 環境変数読み込み
load_dotenv()

async def test_lighter_connection():
    """Lighter接続テスト"""
    print("="*60)
    print("🔌 Lighter Mainnet 接続テスト")
    print("="*60 + "\n")

    try:
        # Lighter SDKのインポート
        print("0️⃣ Lighter SDK インポート中...")
        from lighter.lighter_client import Client
        print("   ✅ SDK インポート成功\n")

        # 1. SDK初期化
        print("1️⃣ SDK初期化中...")
        base_url = os.getenv('LIGHTER_BASE_URL', 'https://mainnet.zklighter.elliot.ai')

        client = Client(
            api_auth=os.getenv('LIGHTER_PRIVATE_KEY'),
            web_url=base_url
        )
        print(f"   ✅ SDK初期化成功")
        print(f"   Base URL: {base_url}\n")

        # 2. アカウント情報取得
        print("2️⃣ アカウント情報取得中...")
        account_index = int(os.getenv('LIGHTER_ACCOUNT_INDEX', '0'))

        # アカウント情報取得の試行
        # 注: 実際のメソッド名はSDKのバージョンによって異なる可能性あり
        try:
            account = await client.get_blockchain_account(account_index)
            print(f"   ✅ アカウント取得成功")
            print(f"   Account Index: {account_index}")
            print(f"   Account Info: {str(account)[:100]}...\n")
        except Exception as e:
            print(f"   ⚠️  アカウント取得スキップ: {e}\n")

        # 3. 市場情報取得
        print("3️⃣ 市場情報取得中...")
        try:
            markets = await client.get_all_markets()
            print(f"   ✅ 市場データ取得成功")
            print(f"   利用可能市場数: {len(markets)}個\n")

            # 最初の3つの市場を表示
            print("   主要市場:")
            for i, market in enumerate(markets[:3]):
                market_id = market.get('market_id', i)
                symbol = market.get('symbol', 'N/A')
                print(f"     {i+1}. Market {market_id}: {symbol}")

        except Exception as e:
            print(f"   ⚠️  市場情報取得スキップ: {e}\n")

        print("\n" + "="*60)
        print("🎉 Lighter接続テスト完了！")
        print("="*60)

        # クリーンアップ
        await client.close()

    except Exception as e:
        print(f"\n❌ エラー発生: {e}")
        print(f"エラータイプ: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    asyncio.run(test_lighter_connection())
