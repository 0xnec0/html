#!/usr/bin/env python3
"""
プロキシ設定検証（接続なし）

実際の接続を行わず、プロキシURLが正しく構築されるか確認
"""
import os
from dotenv import load_dotenv

load_dotenv()

def test_proxy_config():
    """プロキシ設定を検証"""
    print("=" * 60)
    print("🔧 プロキシ設定検証")
    print("=" * 60)
    print()

    # 設定読み込み
    proxy_enabled = os.getenv('PROXY_ENABLED', 'false').lower() == 'true'
    proxy_server = os.getenv('PROXY_SERVER', '')
    proxy_port = os.getenv('PROXY_PORT', '')
    proxy_username = os.getenv('PROXY_USERNAME', '')
    proxy_password = os.getenv('PROXY_PASSWORD', '')

    print("📋 現在の設定:")
    print(f"   PROXY_ENABLED: {proxy_enabled}")
    print(f"   PROXY_SERVER: {proxy_server}")
    print(f"   PROXY_PORT: {proxy_port}")
    print(f"   PROXY_USERNAME: {proxy_username[:10]}... (表示省略)")
    print(f"   PROXY_PASSWORD: {'*' * len(proxy_password)}")
    print()

    if not proxy_enabled:
        print("⚠️  プロキシが無効になっています")
        print()
        print("有効にするには .env で以下を設定:")
        print("   PROXY_ENABLED=true")
        print()
        return

    if not proxy_server or not proxy_port:
        print("❌ プロキシサーバーまたはポートが設定されていません")
        print()
        print(".env で以下を設定してください:")
        print("   PROXY_SERVER=your_proxy_server")
        print("   PROXY_PORT=your_proxy_port")
        print()
        return

    # プロキシURL構築
    if proxy_username and proxy_password:
        proxy_url = f"http://{proxy_username}:{proxy_password}@{proxy_server}:{proxy_port}"
        safe_proxy_url = f"http://{proxy_username}:{'*' * len(proxy_password)}@{proxy_server}:{proxy_port}"
    else:
        proxy_url = f"http://{proxy_server}:{proxy_port}"
        safe_proxy_url = proxy_url

    print("✅ プロキシURL構築成功:")
    print(f"   {safe_proxy_url}")
    print()

    # lighter_signer.pyの関数をテスト
    print("🧪 lighter_signer.get_proxy_url() テスト:")
    try:
        from lighter_signer import get_proxy_url
        result = get_proxy_url()
        if result:
            safe_result = result.split('@')[-1] if '@' in result else result
            print(f"   ✅ 返り値: http://***@{safe_result}")
        else:
            print(f"   ⚠️  返り値: None (プロキシ無効)")
    except Exception as e:
        print(f"   ❌ エラー: {e}")
    print()

    # paradex_client.pyの関数をテスト
    print("🧪 paradex_client.get_proxy_url() テスト:")
    try:
        from paradex_client import get_proxy_url as paradex_get_proxy_url
        result = paradex_get_proxy_url()
        if result:
            safe_result = result.split('@')[-1] if '@' in result else result
            print(f"   ✅ 返り値: http://***@{safe_result}")
        else:
            print(f"   ⚠️  返り値: None (プロキシ無効)")
    except Exception as e:
        print(f"   ❌ エラー: {e}")
    print()

    print("=" * 60)
    print("📊 検証結果")
    print("=" * 60)
    print()

    if proxy_enabled and proxy_server and proxy_port:
        print("✅ プロキシ設定は正常です！")
        print()
        print("次のステップ:")
        print("   1. .envファイルの秘密鍵を設定（LIGHTER_PRIVATE_KEY, PARADEX_L1_PRIVATE_KEY）")
        print("   2. python test_proxy_connection.py で実際の接続テスト")
        print()
    else:
        print("⚠️  プロキシ設定が不完全です")
        print("   .envファイルを確認してください")
        print()


if __name__ == "__main__":
    test_proxy_config()
