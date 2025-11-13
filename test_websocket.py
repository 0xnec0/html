#!/usr/bin/env python3
"""
WebSocket接続テストスクリプト
プロキシ経由でLighter WebSocketに接続できるか確認
"""

import asyncio
import os
import sys

# Add bot directory to path to import config
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bot'))

try:
    from config import Config
    config = Config()
    print("✅ Config読み込み成功")
except Exception as e:
    print(f"❌ Config読み込み失敗: {e}")
    exit(1)

# Import Lighter SDK
try:
    import lighter
    print("✅ Lighter SDK インポート成功")
except ImportError as e:
    print(f"❌ Lighter SDK インポート失敗: {e}")
    exit(1)

# Get configuration
LIGHTER_PRIVATE_KEY = config.lighter_private_key
LIGHTER_ACCOUNT_INDEX = config.lighter_account_index
LIGHTER_API_KEY_INDEX = config.lighter_api_key_index
LIGHTER_MARKET = config.lighter_market

USE_PROXY = config.use_proxy
proxy_url = config.proxy_url

if USE_PROXY and proxy_url:
    print(f"🔒 プロキシ使用: {config.proxy_server}:{config.proxy_port}")
else:
    proxy_url = None
    print("📡 プロキシなし（直接接続）")

print(f"\n設定:")
print(f"  Account Index: {LIGHTER_ACCOUNT_INDEX}")
print(f"  API Key Index: {LIGHTER_API_KEY_INDEX}")
print(f"  Market: {LIGHTER_MARKET}")

# WebSocket callback
def on_account_update(account_id: int, account_state: dict):
    """WebSocketコールバック（同期関数）"""
    print(f"\n✅ WebSocketメッセージ受信!")
    print(f"   Account ID: {account_id}")
    if account_state:
        print(f"   Account State keys: {list(account_state.keys())}")
        if 'positions' in account_state:
            positions = account_state['positions']
            print(f"   Positions: {len(positions)} 件")


async def test_websocket():
    """WebSocket接続テスト"""
    print("\n" + "="*60)
    print("WebSocket接続テスト開始")
    print("="*60)

    try:
        print("\n[1/3] WebSocketクライアント作成中...")
        ws_client = lighter.WsClient(
            account_ids=[LIGHTER_ACCOUNT_INDEX],
            on_account_update=on_account_update,
        )
        print("✅ WebSocketクライアント作成完了")

        print("\n[2/3] WebSocket接続開始...")
        print("⏳ 接続中... (最大30秒待機)")

        # Start WebSocket in background
        ws_task = asyncio.create_task(ws_client.run_async())

        # Wait for connection with timeout
        try:
            await asyncio.wait_for(asyncio.sleep(5), timeout=5.0)
            print("✅ WebSocket接続成功（5秒経過、エラーなし）")
        except asyncio.TimeoutError:
            print("✅ WebSocket接続成功（タイムアウト待機完了）")

        print("\n[3/3] 30秒間メッセージを監視...")
        print("💡 ポジションを変更すると、ここにメッセージが表示されます")
        print("   (Ctrl+C で中断)")

        # Wait for messages
        await asyncio.sleep(30)

        print("\n✅ テスト完了")

    except KeyboardInterrupt:
        print("\n\n⚠️  ユーザーによる中断")
    except Exception as e:
        print(f"\n❌ エラー発生: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*60)
    print("テスト終了")
    print("="*60)


if __name__ == "__main__":
    # Run test
    try:
        asyncio.run(test_websocket())
    except KeyboardInterrupt:
        print("\n\n👋 終了")
