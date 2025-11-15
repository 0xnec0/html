#!/usr/bin/env python3
"""
プロキシ接続テスト

LighterとParadex両方のAPIがプロキシ経由で正常に動作するかテスト
"""
import os
import asyncio
import aiohttp
from dotenv import load_dotenv
from lighter_signer import LighterSigner, get_next_nonce, get_proxy_url
from paradex_client import create_paradex_client

# 環境変数読み込み
load_dotenv()

async def test_lighter_proxy():
    """Lighter API プロキシテスト"""
    print("=" * 60)
    print("🔌 Lighter API プロキシ接続テスト")
    print("=" * 60)
    print()

    proxy_url = get_proxy_url()
    if proxy_url:
        # パスワード部分を隠して表示
        safe_proxy = proxy_url.split('@')[-1]
        print(f"✓ プロキシ有効: {safe_proxy}")
    else:
        print("⚠️  プロキシ無効（直接接続）")
    print()

    try:
        # 1. Lighter Signer初期化
        print("1️⃣ Lighter Signer初期化中...")
        private_key = os.getenv('LIGHTER_PRIVATE_KEY')
        account_index = int(os.getenv('LIGHTER_ACCOUNT_INDEX', '0'))
        api_key_index = int(os.getenv('LIGHTER_API_KEY_INDEX', '6'))

        if not private_key:
            print("❌ LIGHTER_PRIVATE_KEY が設定されていません")
            return False

        signer = LighterSigner(
            private_key=private_key,
            account_index=account_index,
            api_key_index=api_key_index
        )
        print(f"   ✅ Signer初期化成功")
        print(f"   Account Index: {account_index}")
        print()

        # 2. API接続テスト（Nonce取得）
        print("2️⃣ Nonce取得テスト（プロキシ経由API接続）...")
        base_url = "https://mainnet.zklighter.elliot.ai"

        nonce = await get_next_nonce(base_url, account_index, api_key_index)
        print(f"   ✅ Nonce取得成功: {nonce}")
        print()

        # 3. 市場情報取得テスト
        print("3️⃣ 市場情報取得テスト（プロキシ経由）...")
        markets_url = f"{base_url}/api/v1/markets"

        async with aiohttp.ClientSession() as session:
            async with session.get(markets_url, proxy=proxy_url) as response:
                if response.status == 200:
                    markets_data = await response.json()
                    markets = markets_data.get('markets', [])
                    print(f"   ✅ 市場データ取得成功")
                    print(f"   市場数: {len(markets)}個")

                    # 最初の3市場を表示
                    if markets:
                        print()
                        print("   主要市場:")
                        for i, market in enumerate(markets[:3]):
                            symbol = market.get('symbol', 'N/A')
                            market_id = market.get('id', 'N/A')
                            print(f"     {i+1}. {symbol} (ID: {market_id})")
                else:
                    text = await response.text()
                    print(f"   ❌ 市場データ取得失敗: HTTP {response.status}")
                    print(f"   {text}")
                    return False

        print()
        print("=" * 60)
        print("✅ Lighter プロキシ接続テスト成功！")
        print("=" * 60)
        print()
        return True

    except Exception as e:
        print(f"\n❌ Lighter プロキシテストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_paradex_proxy():
    """Paradex API プロキシテスト"""
    print("=" * 60)
    print("🔌 Paradex API プロキシ接続テスト")
    print("=" * 60)
    print()

    proxy_url = get_proxy_url()
    if proxy_url:
        safe_proxy = proxy_url.split('@')[-1]
        print(f"✓ プロキシ有効: {safe_proxy}")
    else:
        print("⚠️  プロキシ無効（直接接続）")
    print()

    try:
        # 1. Paradex クライアント初期化（プロキシ設定自動適用）
        print("1️⃣ Paradex クライアント初期化中...")
        paradex = create_paradex_client()

        print(f"   ✅ クライアント初期化成功")
        print(f"   L2 Address: {hex(paradex.account.l2_address)}")
        print()

        # 2. 市場情報取得テスト
        print("2️⃣ 市場情報取得テスト（プロキシ経由）...")
        markets = paradex.api_client.fetch_markets()

        if isinstance(markets, dict) and 'results' in markets:
            markets_list = markets['results']
        elif isinstance(markets, list):
            markets_list = markets
        else:
            markets_list = []

        print(f"   ✅ 市場データ取得成功")
        print(f"   市場数: {len(markets_list)}個")

        # 最初の3市場を表示
        if markets_list:
            print()
            print("   主要市場:")
            for i, market in enumerate(markets_list[:3]):
                symbol = market.get('symbol', 'N/A')
                print(f"     {i+1}. {symbol}")

        print()

        # 3. アカウント残高取得テスト
        print("3️⃣ アカウント残高取得テスト（プロキシ経由）...")
        try:
            summary = paradex.api_client.fetch_account_summary()
            if isinstance(summary, dict):
                equity = summary.get('equity', 0)
                print(f"   ✅ 残高取得成功")
                print(f"   アカウント資産: ${equity}")
            else:
                print(f"   ✅ サマリ取得成功: {summary}")
        except Exception as e:
            print(f"   ⚠️  残高取得エラー: {e}")

        print()
        print("=" * 60)
        print("✅ Paradex プロキシ接続テスト成功！")
        print("=" * 60)
        print()
        return True

    except Exception as e:
        print(f"\n❌ Paradex プロキシテストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """メインテスト実行"""
    print("\n")
    print("🧪 プロキシ接続総合テスト")
    print("=" * 60)
    print()

    # プロキシ設定状態確認
    proxy_enabled = os.getenv('PROXY_ENABLED', 'false').lower() == 'true'
    if proxy_enabled:
        proxy_server = os.getenv('PROXY_SERVER', '')
        proxy_port = os.getenv('PROXY_PORT', '')
        print(f"📡 プロキシ設定: {proxy_server}:{proxy_port}")
        print(f"   タイプ: レジデンシャルプロキシ")
    else:
        print("📡 プロキシ設定: 無効（直接接続モード）")
        print()
        print("💡 プロキシを有効にするには:")
        print("   1. .envファイルでPROXY_ENABLED=trueに設定")
        print("   2. PROXY_SERVER, PROXY_PORT, PROXY_USERNAME, PROXY_PASSWORDを設定")

    print()
    print("-" * 60)
    print()

    # Lighterテスト
    lighter_ok = await test_lighter_proxy()

    print()

    # Paradexテスト
    paradex_ok = test_paradex_proxy()

    print()
    print("=" * 60)
    print("📊 テスト結果サマリ")
    print("=" * 60)
    print()
    print(f"Lighter API:  {'✅ 成功' if lighter_ok else '❌ 失敗'}")
    print(f"Paradex API:  {'✅ 成功' if paradex_ok else '❌ 失敗'}")
    print()

    if lighter_ok and paradex_ok:
        print("🎉 すべてのプロキシ接続テストが成功しました！")
        print()
        if proxy_enabled:
            print("✓ 両取引所がプロキシ経由で正常に動作しています")
        else:
            print("✓ 両取引所が直接接続で正常に動作しています")
        print("✓ グリッドボット開発を続行できます")
    else:
        print("⚠️  一部のテストが失敗しました")
        print("   エラーメッセージを確認して設定を見直してください")

    print()


if __name__ == "__main__":
    asyncio.run(main())
