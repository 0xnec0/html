#!/usr/bin/env python3
"""
Lighter WebSocket接続テスト - REST API版
目的: WebSocketで注文約定イベントをリアルタイム受信できるか確認

使い方:
1. まずLighterで小額の指値注文を出す
2. このスクリプトを実行
3. 注文が約定すると WebSocket経由でイベントを受信
"""
import os
import asyncio
import json
import websockets
from dotenv import load_dotenv
from eth_account import Account
from eth_account.messages import encode_defunct

# 環境変数読み込み
load_dotenv()

async def test_lighter_websocket():
    """Lighter WebSocket接続テスト"""
    print("="*60)
    print("🔌 Lighter WebSocket 接続テスト (REST API)")
    print("="*60 + "\n")

    try:
        # 1. 認証情報準備
        print("1️⃣ 認証情報準備中...")
        private_key = os.getenv('LIGHTER_PRIVATE_KEY')
        account_index = int(os.getenv('LIGHTER_ACCOUNT_INDEX', '0'))

        if not private_key:
            raise ValueError("LIGHTER_PRIVATE_KEYが設定されていません")

        # アカウント作成
        account = Account.from_key(private_key)
        print(f"   ✅ アカウント準備完了")
        print(f"   Address: {account.address}")
        print(f"   Account Index: {account_index}\n")

        # 2. WebSocket接続
        print("2️⃣ WebSocket接続中...")

        # Lighter WebSocketエンドポイント（wss://）
        base_url = os.getenv('LIGHTER_BASE_URL', 'https://mainnet.zklighter.elliot.ai')
        ws_url = base_url.replace('https://', 'wss://').replace('http://', 'ws://')

        # WebSocketエンドポイント
        # 注: 実際のエンドポイントはLighter APIドキュメントを参照
        ws_endpoint = f"{ws_url}/ws"

        print(f"   WebSocket URL: {ws_endpoint}")

        # イベント受信カウンター
        event_count = 0

        try:
            async with websockets.connect(ws_endpoint, ping_interval=20, ping_timeout=10) as websocket:
                print("   ✅ WebSocket接続成功\n")

                # 3. 認証メッセージ送信（必要な場合）
                print("3️⃣ 認証中...")

                # 認証メッセージの署名（Lighter APIの仕様に合わせる）
                # 注: 実際の認証フォーマットはAPIドキュメント参照
                auth_message = {
                    "type": "authenticate",
                    "account_index": account_index,
                    "address": account.address,
                }

                # メッセージを送信
                await websocket.send(json.dumps(auth_message))
                print(f"   ✅ 認証メッセージ送信完了\n")

                # 4. チャンネル購読
                print("4️⃣ チャンネル購読中...")

                # アカウント更新を購読
                subscribe_message = {
                    "type": "subscribe",
                    "channels": [
                        f"account.{account_index}",  # アカウント更新
                        "trades",  # 約定イベント
                        "fills",   # フィルイベント
                    ]
                }

                await websocket.send(json.dumps(subscribe_message))
                print("   ✅ チャンネル購読完了")
                print(f"   購読中: account.{account_index}, trades, fills\n")

                # 5. イベント監視（60秒間）
                print("5️⃣ イベント監視中（60秒間）...")
                print("   💡 この間に注文が約定すればイベントが届きます")
                print("   💡 Ctrl+C で中断できます\n")

                start_time = asyncio.get_event_loop().time()
                timeout = 60  # 60秒間監視

                try:
                    while True:
                        # タイムアウトチェック
                        elapsed = asyncio.get_event_loop().time() - start_time
                        if elapsed >= timeout:
                            print(f"\n   ⏱️  {timeout}秒経過、監視終了")
                            break

                        # 10秒ごとに進捗表示
                        if int(elapsed) % 10 == 0 and int(elapsed) > 0:
                            print(f"   ⏱️  {int(elapsed)}秒経過... (受信イベント数: {event_count})")

                        # メッセージ受信（タイムアウト付き）
                        try:
                            message = await asyncio.wait_for(
                                websocket.recv(),
                                timeout=1.0
                            )

                            # メッセージ解析
                            try:
                                data = json.loads(message)
                                event_count += 1

                                # イベントタイプ別に表示
                                event_type = data.get('type', 'unknown')

                                if event_type == 'account_update':
                                    print(f"\n📨 【イベント {event_count}】アカウント更新受信:")
                                    print(f"   タイムスタンプ: {data.get('timestamp', 'N/A')}")

                                    # ポジション情報があれば表示
                                    if 'positions' in data:
                                        positions = data['positions']
                                        print(f"   ポジション数: {len(positions)}")
                                        for pos in positions[:3]:
                                            print(f"     - Market: {pos.get('market_id', 'N/A')}, Size: {pos.get('size', 'N/A')}")

                                elif event_type == 'trade' or event_type == 'fill':
                                    print(f"\n🎯 【約定イベント {event_count}】受信:")
                                    print(f"   Trade ID: {data.get('trade_id', 'N/A')}")
                                    print(f"   Market: {data.get('market_id', 'N/A')}")
                                    print(f"   Side: {data.get('side', 'N/A')}")
                                    print(f"   Size: {data.get('size', 'N/A')}")
                                    print(f"   Price: {data.get('price', 'N/A')}")

                                else:
                                    # その他のイベント
                                    print(f"\n📩 【イベント {event_count}】{event_type}:")
                                    print(f"   データ: {str(data)[:200]}...")

                            except json.JSONDecodeError:
                                # JSON以外のメッセージ（pingなど）
                                pass

                        except asyncio.TimeoutError:
                            # 1秒以内にメッセージがない場合は継続
                            pass

                except KeyboardInterrupt:
                    print("\n\n   ⚠️  ユーザーによって中断されました")

                print(f"\n   📊 監視終了: 合計 {event_count} 件のイベントを受信")

        except websockets.exceptions.WebSocketException as e:
            print(f"\n   ⚠️  WebSocket接続エラー: {e}")
            print("\n   💡 ヒント:")
            print("      - Lighter WebSocketエンドポイントが正しいか確認")
            print("      - インターネット接続を確認")
            print("      - ファイアウォール設定を確認")
            raise

        print("\n" + "="*60)
        print("🎉 WebSocketテスト完了！")
        print("="*60)

        print("\n📝 次のステップ:")
        print("   1. 実際の注文を出してフィルイベントを確認")
        print("   2. WebSocket切断時の再接続ロジックを追加")
        print("   3. 本番ボットに統合")

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
