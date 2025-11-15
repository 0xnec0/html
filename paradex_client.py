#!/usr/bin/env python3
"""
Paradex クライアントヘルパー（プロキシサポート付き）

Paradex SDKはHTTP_PROXY/HTTPS_PROXY環境変数を使用するため、
このモジュールでプロキシ設定を一元管理する。
"""
import os
from typing import Optional
from dotenv import load_dotenv
from paradex_py import Paradex
from paradex_py.environment import PROD

def get_proxy_url() -> Optional[str]:
    """
    環境変数からプロキシURLを構築

    Returns:
        プロキシURL（無効の場合None）
    """
    load_dotenv()

    proxy_enabled = os.getenv('PROXY_ENABLED', 'false').lower() == 'true'
    if not proxy_enabled:
        return None

    server = os.getenv('PROXY_SERVER', '')
    port = os.getenv('PROXY_PORT', '')
    username = os.getenv('PROXY_USERNAME', '')
    password = os.getenv('PROXY_PASSWORD', '')

    if not server or not port:
        return None

    if username and password:
        return f"http://{username}:{password}@{server}:{port}"
    else:
        return f"http://{server}:{port}"


def create_paradex_client(
    l1_address: Optional[str] = None,
    l1_private_key: Optional[str] = None,
    env=PROD
) -> Paradex:
    """
    プロキシ設定付きParadexクライアントを作成

    Args:
        l1_address: Ethereum L1アドレス（環境変数から取得可能）
        l1_private_key: Ethereum L1秘密鍵（環境変数から取得可能）
        env: Paradex環境（デフォルト: PROD）

    Returns:
        設定済みParadexクライアント
    """
    load_dotenv()

    # 環境変数から取得（引数で上書き可能）
    l1_address = l1_address or os.getenv('PARADEX_L1_ADDRESS')
    l1_private_key = l1_private_key or os.getenv('PARADEX_L1_PRIVATE_KEY')

    if not l1_address or not l1_private_key:
        raise ValueError("PARADEX_L1_ADDRESS and PARADEX_L1_PRIVATE_KEY are required")

    # プロキシ設定
    proxy_url = get_proxy_url()
    if proxy_url:
        # 標準的なHTTPプロキシ環境変数を設定
        # Paradex SDKが内部で使用するHTTPクライアント（requests等）が自動的に認識
        os.environ['HTTP_PROXY'] = proxy_url
        os.environ['HTTPS_PROXY'] = proxy_url
        print(f"✓ Paradex proxy enabled: {proxy_url.split('@')[-1]}")  # パスワード部分を隠す
    else:
        # プロキシ無効の場合は環境変数をクリア
        os.environ.pop('HTTP_PROXY', None)
        os.environ.pop('HTTPS_PROXY', None)

    # Paradexクライアント作成
    paradex = Paradex(
        env=env,
        l1_address=l1_address,
        l1_private_key=l1_private_key
    )

    return paradex


if __name__ == "__main__":
    # 簡単なテスト
    print("=" * 60)
    print("🔌 Paradex クライアント（プロキシ付き）テスト")
    print("=" * 60)
    print()

    try:
        # プロキシ設定付きクライアント作成
        paradex = create_paradex_client()

        print("✅ Paradexクライアント初期化成功")
        print(f"   L2 Address: {hex(paradex.account.l2_address)}")
        print()

        # 市場情報取得テスト
        print("📊 市場情報取得中...")
        markets = paradex.api_client.fetch_markets()

        if isinstance(markets, dict) and 'results' in markets:
            markets_list = markets['results']
        elif isinstance(markets, list):
            markets_list = markets
        else:
            markets_list = []

        print(f"✅ 市場数: {len(markets_list)}個")
        print()

        # 最初の3市場を表示
        if markets_list:
            print("主要市場:")
            for i, market in enumerate(markets_list[:3]):
                symbol = market.get('symbol', 'N/A')
                print(f"  {i+1}. {symbol}")

        print()
        print("=" * 60)
        print("🎉 テスト完了！")
        print("=" * 60)

    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()
