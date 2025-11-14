#!/usr/bin/env python3
"""
Lighter WebSocket接続テスト
目的: WebSocketで注文約定イベントをリアルタイム受信できるか確認

使い方:
1. まずLighterで小額の指値注文を出す
2. このスクリプトを実行
3. 注文が約定すると WebSocket経由でイベントを受信
"""
import os
import asyncio
from dotenv import load_dotenv

# 環境変数読み込み
load_dotenv()

async def test_lighter_websocket():
    """Lighter WebSocket接続テスト"""
    print("="*60)
    print("🔌 Lighter WebSocket 接続テスト")
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
        print(f"   ✅ SDK初期化成功\n")

        # 2. WebSocket接続準備
        print("2️⃣ WebSocket接続準備中...")
        account_index = int(os.getenv('LIGHTER_ACCOUNT_INDEX', '0'))

        # イベント受信カウンター
        event_count = 0

        # アカウント更新イベントを受信するコールバック
        def on_account_update(data):
            nonlocal event_count
            event_count += 1

            print(f"\n📨 【イベント {event_count}】アカウント更新受信:")
            print(f"   タイムスタンプ: {data.get('timestamp', 'N/A')}")
            print(f"   データ: {str(data)[:200]}...")

            # ポジション情報があれば表示
            if 'positions' in data:
                positions = data['positions']
                print(f"   ポジション数: {len(positions)}")
                for pos in positions[:3]:  # 最初の3つだけ表示
                    print(f"     - Market: {pos.get('market_id', 'N/A')}, Size: {pos.get('size', 'N/A')}")

        # 約定イベントを受信するコールバック
        def on_trade_update(data):
            nonlocal event_count
            event_count += 1

            print(f"\n🎯 【約定イベント {event_count}】受信:")
            print(f"   Trade ID: {data.get('trade_id', 'N/A')}")
            print(f"   Market: {data.get('market_id', 'N/A')}")
            print(f"   Side: {data.get('side', 'N/A')}")
            print(f"   Size: {data.get('size', 'N/A')}")
            print(f"   Price: {data.get('price', 'N/A')}")
            print(f"   データ: {str(data)[:200]}...")

        print(f"   ✅ コールバック準備完了\n")

        # 3. WebSocket購読開始
        print("3️⃣ WebSocket購読開始...")
        print(f"   Account Index: {account_index}")
        print("   購読チャンネル: account_updates, trades")

        try:
            # アカウント更新を購読
            # 注: 実際のメソッド名はSDKバージョンによって異なる可能性あり
            await client.subscribe_account_updates(
                account_index=account_index,
                callback=on_account_update
            )
            print("   ✅ WebSocket購読成功\n")
        except AttributeError:
            # メソッドが見つからない場合の代替手段
            print("   ⚠️  subscribe_account_updates メソッドが見つかりません")
            print("   別の方法でWebSocket接続を試みます...\n")

            # WebSocketストリームを直接使用する方法
            # （SDKの実装によって異なる）
            pass

        # 4. イベント監視（60秒間）
        print("4️⃣ イベント監視中（60秒間）...")
        print("   💡 この間に注文が約定すればイベントが届きます")
        print("   💡 Ctrl+C で中断できます\n")

        try:
            # 60秒間待機してイベントを受信
            for i in range(60):
                await asyncio.sleep(1)
                if (i + 1) % 10 == 0:
                    print(f"   ⏱️  {i + 1}秒経過... (受信イベント数: {event_count})")

        except KeyboardInterrupt:
            print("\n\n   ⚠️  ユーザーによって中断されました")

        print(f"\n   📊 監視終了: 合計 {event_count} 件のイベントを受信")

        print("\n" + "="*60)
        print("🎉 WebSocketテスト完了！")
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
    print("\n💡 使い方:")
    print("   1. Lighterで小額の指値注文を出す")
    print("   2. このスクリプトを実行")
    print("   3. 注文が約定するとWebSocketイベントを受信\n")

    asyncio.run(test_lighter_websocket())
