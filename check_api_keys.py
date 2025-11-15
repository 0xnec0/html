#!/usr/bin/env python3
"""
Lighterアカウントの登録済みAPIキーを確認
"""
import asyncio
import aiohttp
import os
from dotenv import load_dotenv

load_dotenv()

async def check_api_keys():
    base_url = "https://mainnet.zklighter.elliot.ai"
    l1_address = "0x847Eb20faFf60fF6a8fba77075B6671756A6f816"

    print("="*60)
    print("🔍 Lighter APIキー確認")
    print("="*60)
    print(f"\nL1 Address: {l1_address}\n")

    # アカウント情報取得
    url = f"{base_url}/api/v1/accountsByL1Address?l1_address={l1_address}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                text = await response.text()
                print(f"❌ エラー: HTTP {response.status}: {text}")
                return

            data = await response.json()
            accounts = data.get('sub_accounts', [])

            if not accounts:
                print("❌ アカウントが見つかりません")
                return

            print(f"✅ {len(accounts)}個のアカウントが見つかりました\n")

            for acc in accounts:
                acc_index = acc.get('account_index')
                acc_type = acc.get('account_type')

                print("="*60)
                print(f"📊 Account Index: {acc_index}")
                print(f"   Type: {acc_type} ({'Main' if acc_type == 0 else 'Sub'})")
                print("-"*60)

                # APIキーリストを取得
                # Note: この情報はAPI経由では取得できない可能性がある
                # 代わりに、現在の.envのAPIキーが有効か確認

                if acc_index == 219718:  # ユーザーのメインアカウント
                    print("\n   🎯 これがあなたのメインアカウントです！")
                    print()
                    print("   📝 .envファイルの設定:")

                    lighter_api_key = os.getenv('LIGHTER_PRIVATE_KEY', '')
                    api_key_index = os.getenv('LIGHTER_API_KEY_INDEX', '6')

                    print(f"   - LIGHTER_PRIVATE_KEY: {lighter_api_key[:6]}...{lighter_api_key[-4:]} ({len(lighter_api_key)}文字)")
                    print(f"   - LIGHTER_API_KEY_INDEX: {api_key_index}")
                    print()

                    if len(lighter_api_key) == 80:
                        print("   ✅ APIキーの長さは正しい（40バイト = 80文字）")
                    else:
                        print(f"   ❌ APIキーの長さが不正（期待: 80文字, 実際: {len(lighter_api_key)}文字）")

                    print()
                    print("   ⚠️ 重要:")
                    print("   このAPIキーがLighterアカウントに登録されているか確認してください。")
                    print()
                    print("   登録方法:")
                    print("   1. Lighter WebサイトまたはAPIを使用")
                    print("   2. Public Keyを生成してアカウントに追加")
                    print("   3. api_key_indexを記録")
                    print()

                print()

if __name__ == "__main__":
    asyncio.run(check_api_keys())
