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

        # "0x"プレフィックスを削除
        if private_key.startswith('0x') or private_key.startswith('0X'):
            private_key = private_key[2:]

        print(f"   🔍 秘密鍵長: {len(private_key)}文字（期待値: 64文字）")

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

        # WebSocketエンドポイント（Lighter公式: /stream）
        ws_endpoint = f"{ws_url}/stream"

        print(f"   WebSocket URL: {ws_endpoint}")

        # イベント受信カウンター
        event_count = 0

        try:
            async with websockets.connect(ws_endpoint, ping_interval=20, ping_timeout=10) as websocket:
                print("   ✅ WebSocket接続成功\n")

                # 3. チャンネル購読（Lighter公式形式）
                print("3️⃣ チャンネル購読中...")

                # アカウント更新を購読（公式形式: channel単数形）
                # アカウント全体の更新を購読
                account_subscribe = {
                    "type": "subscribe",
                    "channel": f"account_all/{account_index}"
                }
                await websocket.send(json.dumps(account_subscribe))
                print(f"   📡 購読: account_all/{account_index}")

                # オーダーブック購読（例: market_id=0のBTC-USD-PERPなど）
                # 注: 実際の取引で使うmarket_idに変更する
                orderbook_subscribe = {
                    "type": "subscribe",
                    "channel": "order_book/0"
                }
                await websocket.send(json.dumps(orderbook_subscribe))
                print(f"   📡 購読: order_book/0")

                print("   ✅ チャンネル購読完了\n")

                # 4. イベント監視（60秒間）
                print("4️⃣ イベント監視中（60秒間）...")
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

                                # イベントタイプ別に表示（Lighter公式形式）
                                event_type = data.get('type', 'unknown')

                                # pingはカウントしない
                                if event_type != 'ping':
                                    event_count += 1

                                if event_type == 'connected':
                                    print(f"\n✅ 【接続確認】セッションID: {data.get('session_id', 'N/A')}")

                                elif event_type == 'subscribed/account_all':
                                    print(f"\n✅ 【購読確認】アカウント購読成功")

                                elif event_type == 'subscribed/order_book':
                                    print(f"\n✅ 【購読確認】オーダーブック購読成功")

                                elif event_type == 'update/account_all':
                                    print(f"\n📨 【イベント {event_count}】アカウント更新受信:")
                                    # アカウントデータを表示
                                    if 'data' in data:
                                        account_data = data['data']
                                        print(f"   データ: {str(account_data)[:200]}...")

                                elif event_type == 'update/order_book':
                                    print(f"\n📊 【イベント {event_count}】オーダーブック更新:")
                                    if 'data' in data:
                                        ob_data = data['data']
                                        asks = ob_data.get('asks', [])
                                        bids = ob_data.get('bids', [])
                                        print(f"   Asks: {len(asks)}個, Bids: {len(bids)}個")

                                elif event_type == 'ping':
                                    # Pingに応答
                                    await websocket.send(json.dumps({"type": "pong"}))
                                    # pingは表示しない（多すぎるため）

                                else:
                                    # その他のイベント（エラーなど）
                                    print(f"\n📩 【イベント {event_count}】{event_type}:")
                                    print(f"   データ: {str(data)[:200]}...")

                            except json.JSONDecodeError:
                                # JSON以外のメッセージ
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
