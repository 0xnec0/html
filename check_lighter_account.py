#!/usr/bin/env python3
"""
Lighterアカウント確認スクリプト

目的: L1アドレスに関連するLighterアカウントを確認し、
     有効なaccount_indexを取得する
"""
import os
import asyncio
import aiohttp
from dotenv import load_dotenv
from eth_account import Account

# 環境変数読み込み
load_dotenv()

async def check_lighter_accounts():
    """Lighterアカウント確認"""
    print("="*60)
    print("🔍 Lighterアカウント確認")
    print("="*60 + "\n")

    # 秘密鍵からL1アドレスを取得
    private_key = os.getenv('LIGHTER_PRIVATE_KEY')
    if not private_key:
        print("❌ LIGHTER_PRIVATE_KEYが設定されていません")
        return

    # 0xプレフィックス削除
    if private_key.startswith('0x') or private_key.startswith('0X'):
        private_key = private_key[2:]

    # L1アドレス取得
    account = Account.from_key(private_key)
    l1_address = account.address

    print(f"📊 あなたのL1アドレス: {l1_address}\n")

    # Lighter APIでアカウント確認
    base_url = os.getenv('LIGHTER_BASE_URL', 'https://mainnet.zklighter.elliot.ai')
    url = f"{base_url}/api/v1/accountsByL1Address?l1_address={l1_address}"

    print(f"1️⃣ Lighterアカウント検索中...")
    print(f"   URL: {url}\n")

    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status == 200:
                data = await response.json()

                print(f"   ✅ API応答成功")
                print(f"   レスポンス: {data}\n")

                # アカウントリスト確認
                if isinstance(data, dict):
                    accounts = data.get('accounts', [])

                    if accounts:
                        print(f"✅ {len(accounts)}個のアカウントが見つかりました！\n")

                        for i, acc in enumerate(accounts):
                            acc_index = acc.get('index', acc.get('account_index', 'N/A'))
                            print(f"   アカウント {i+1}:")
                            print(f"      Index: {acc_index}")
                            print(f"      データ: {acc}\n")

                        # 推奨account_index
                        first_index = accounts[0].get('index', accounts[0].get('account_index', 0))
                        print("="*60)
                        print("📝 推奨設定:")
                        print("="*60)
                        print(f"\n.envファイルに以下を設定してください:")
                        print(f"LIGHTER_ACCOUNT_INDEX={first_index}")
                        print("\nまたは:")
                        print(f"export LIGHTER_ACCOUNT_INDEX={first_index}")

                    else:
                        print("❌ アカウントが見つかりませんでした\n")
                        print("="*60)
                        print("🔧 解決方法:")
                        print("="*60)
                        print("\nLighterでアカウントを作成する必要があります。")
                        print("\n方法1: Lighter UIから作成")
                        print("   1. https://app.lighter.xyz/ にアクセス")
                        print(f"   2. L1アドレス {l1_address} でウォレット接続")
                        print("   3. アカウントを作成")
                        print("\n方法2: API経由で作成（高度）")
                        print("   /api/v1/createAccount エンドポイントを使用")
                        print("   詳細: https://apidocs.lighter.xyz/")

                else:
                    print(f"⚠️  予期しないレスポンス形式: {data}")

            elif response.status == 404:
                print(f"   ⚠️  アカウントが見つかりません（HTTP 404）\n")
                print("="*60)
                print("🔧 解決方法:")
                print("="*60)
                print("\nLighterでアカウントを作成してください:")
                print(f"   1. https://app.lighter.xyz/ にアクセス")
                print(f"   2. L1アドレス {l1_address} でウォレット接続")
                print("   3. アカウントを作成")

            else:
                text = await response.text()
                print(f"   ❌ HTTP {response.status}: {text}")

if __name__ == "__main__":
    asyncio.run(check_lighter_accounts())
