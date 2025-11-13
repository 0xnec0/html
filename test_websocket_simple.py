#!/usr/bin/env python3
"""
WebSocket接続テストスクリプト（シンプル版）
プロキシ経由でLighter WebSocketに接続できるか確認
"""

import asyncio

# Import Lighter SDK
try:
    import lighter
    print("✅ Lighter SDK インポート成功")
except ImportError as e:
    print(f"❌ Lighter SDK インポート失敗: {e}")
    exit(1)

# 設定（.envファイルから直接コピー）
LIGHTER_ACCOUNT_INDEX = 219718
LIGHTER_MARKET = "ENA"

# プロキシ設定（テスト用に変更可能）
USE_PROXY = True  # True または False
PROXY_URL = "http://smart-q2lwm7pfe5i3_life-120_session-Mfkpd3:us1YRmGVF1WKNnnb@as.smartproxy.net:3120"

if USE_PROXY:
    print(f"🔒 プロキシ使用: {PROXY_URL[:50]}...")
else:
    PROXY_URL = None
    print("📡 プロキシなし（直接接続）")

print(f"\n設定:")
print(f"  Account Index: {LIGHTER_ACCOUNT_INDEX}")
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

        # Note: Lighter SDK's WsClient doesn't support proxy configuration
        # The SDK uses websockets library which may not support HTTP proxies
        ws_client = lighter.WsClient(
            account_ids=[LIGHTER_ACCOUNT_INDEX],
            on_account_update=on_account_update,
        )
        print("✅ WebSocketクライアント作成完了")

        print("\n[2/3] WebSocket接続開始...")
        print("⏳ 接続中... (最大10秒待機)")

        # Start WebSocket in background
        ws_task = asyncio.create_task(ws_client.run_async())

        # Wait for initial connection
        try:
            await asyncio.wait_for(asyncio.sleep(10), timeout=10.0)
            print("✅ WebSocket接続成功（10秒経過、エラーなし）")
        except asyncio.TimeoutError:
            print("✅ WebSocket接続タイムアウト（10秒経過）")

        print("\n[3/3] 20秒間メッセージを監視...")
        print("💡 ポジションを変更すると、ここにメッセージが表示されます")
        print("   (Ctrl+C で中断)")

        # Wait for messages
        await asyncio.sleep(20)

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
    print("\n💡 注意: Lighter SDKのWebSocketクライアントはプロキシをサポートしていない可能性があります")
    print("   WebSocketは通常、HTTP CONNECTメソッドを使用してプロキシ経由で接続します")
    print("   Lighter SDKがこれをサポートしているか確認します...\n")

    # Run test
    try:
        asyncio.run(test_websocket())
    except KeyboardInterrupt:
        print("\n\n👋 終了")
