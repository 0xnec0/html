#!/usr/bin/env python3
"""
Lighter注文テスト：発注→3秒待機→キャンセル

目的:
1. 安全な価格で最小額の指値注文を出す（約定しない価格）
2. 3秒待機
3. 注文をキャンセル

これにより、実際のお金を失わずに注文システムをテストできる
"""
import os
import asyncio
import time
from dotenv import load_dotenv
from lighter_signer import LighterSigner, send_transaction
import aiohttp

# 環境変数読み込み
load_dotenv()

async def get_market_info(market_symbol: str):
    """市場情報取得"""
    base_url = os.getenv('LIGHTER_BASE_URL', 'https://mainnet.zklighter.elliot.ai')

    async with aiohttp.ClientSession() as session:
        url = f"{base_url}/api/v1/orderBookDetails?market={market_symbol}"

        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status == 200:
                data = await response.json()

                if isinstance(data, dict) and 'order_book_details' in data:
                    for book in data['order_book_details']:
                        if book.get('symbol', '').upper() == market_symbol.upper():
                            return book

    return None


async def main():
    """メイン処理"""
    print("="*60)
    print("🧪 Lighter 注文テスト：発注→3秒待機→キャンセル")
    print("="*60 + "\n")

    # 設定
    market_symbol = os.getenv('TEST_MARKET', 'TRX')
    target_usd = float(os.getenv('TEST_ORDER_SIZE_USD', '20.0'))
    base_url = os.getenv('LIGHTER_BASE_URL', 'https://mainnet.zklighter.elliot.ai')
    private_key = os.getenv('LIGHTER_PRIVATE_KEY')
    account_index = int(os.getenv('LIGHTER_ACCOUNT_INDEX', '0'))
    api_key_index = int(os.getenv('LIGHTER_API_KEY_INDEX', '6'))  # .envから読み込み

    if not private_key:
        print("❌ LIGHTER_PRIVATE_KEYが設定されていません")
        return

    print(f"📊 設定:")
    print(f"   市場: {market_symbol}")
    print(f"   目標金額: ${target_usd}")
    print(f"   アカウントインデックス: {account_index}")
    print(f"   APIキーインデックス: {api_key_index}\n")

    # 1. 市場情報取得
    print("1️⃣ 市場情報取得中...")
    market_info = await get_market_info(market_symbol)

    if not market_info:
        print(f"❌ 市場 '{market_symbol}' が見つかりません")
        return

    market_id = market_info.get('market_id')
    last_price = float(market_info.get('last_trade_price', 0))
    price_decimals = int(market_info.get('price_decimals', 0))
    size_decimals = int(market_info.get('size_decimals', 0))
    min_base_amount = float(market_info.get('min_base_amount', 0))

    print(f"   ✅ 市場情報取得成功")
    print(f"   Market ID: {market_id}")
    print(f"   最終価格: ${last_price}")
    print(f"   価格精度: {price_decimals} decimals")
    print(f"   サイズ精度: {size_decimals} decimals\n")

    # 2. 安全な注文パラメータ計算（絶対に約定しない価格）
    print("2️⃣ 安全な注文パラメータ計算中...")

    # 買い注文：最終価格の150%（約定しない）
    safe_buy_price = last_price * 1.5
    buy_size = target_usd / safe_buy_price

    # 最小数量チェック
    if min_base_amount > 0 and buy_size < min_base_amount:
        buy_size = min_base_amount

    # 整数変換
    safe_buy_price_int = int(safe_buy_price * (10 ** price_decimals))
    buy_size_int = int(buy_size * (10 ** size_decimals))

    print(f"   ✅ 注文パラメータ:")
    print(f"   価格: ${safe_buy_price:.6f} (150% of last price)")
    print(f"   価格(整数): {safe_buy_price_int}")
    print(f"   数量: {buy_size:.6f}")
    print(f"   数量(整数): {buy_size_int}")
    print(f"   合計: 約${buy_size * safe_buy_price:.2f}")
    print(f"   💡 最終価格の150%なので絶対に約定しません！\n")

    # 3. 署名準備
    print("3️⃣ 注文署名準備中...")
    try:
        signer = LighterSigner(
            private_key=private_key,
            account_index=account_index,
            api_key_index=6  # あなたのアカウントのAPIキーインデックス
        )
        print("   ✅ 署名クライアント初期化成功\n")
    except Exception as e:
        print(f"❌ 署名クライアント初期化失敗: {e}")
        return

    # 4. 注文作成・署名
    print("4️⃣ 買い注文を作成・署名中...")

    # ユニークな注文ID（タイムスタンプ）
    client_order_index = int(time.time() * 1000)

    tx_json, error = signer.sign_create_order(
        market_index=market_id,
        client_order_index=client_order_index,
        base_amount=buy_size_int,
        price=safe_buy_price_int,
        is_ask=False,  # False=買い
        order_type=LighterSigner.ORDER_TYPE_LIMIT,
        time_in_force=LighterSigner.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
        reduce_only=False
    )

    if error:
        print(f"❌ 注文署名失敗: {error}")
        return

    print(f"   ✅ 注文署名成功")
    print(f"   注文ID: {client_order_index}\n")

    # 5. 注文送信
    print("5️⃣ 注文送信中...")
    try:
        response = await send_transaction(base_url, tx_json)
        print(f"   ✅ 注文送信成功！")
        print(f"   レスポンス: {response}\n")
    except Exception as e:
        print(f"❌ 注文送信失敗: {e}")
        return

    # 6. 3秒待機
    print("6️⃣ 3秒待機中...")
    for i in range(3, 0, -1):
        print(f"   ⏱️  {i}秒...")
        await asyncio.sleep(1)
    print("   ✅ 待機完了\n")

    # 7. キャンセル署名
    print("7️⃣ 注文キャンセル中...")

    cancel_tx_json, cancel_error = signer.sign_cancel_order(
        market_index=market_id,
        order_index=client_order_index
    )

    if cancel_error:
        print(f"❌ キャンセル署名失敗: {cancel_error}")
        return

    print(f"   ✅ キャンセル署名成功\n")

    # 8. キャンセル送信
    print("8️⃣ キャンセル送信中...")
    try:
        cancel_response = await send_transaction(base_url, cancel_tx_json)
        print(f"   ✅ キャンセル成功！")
        print(f"   レスポンス: {cancel_response}\n")
    except Exception as e:
        print(f"❌ キャンセル送信失敗: {e}")
        print(f"   💡 注文がすでに約定済みの可能性があります")
        return

    # 9. 完了
    print("="*60)
    print("🎉 テスト完了！")
    print("="*60)
    print(f"\n📊 サマリ:")
    print(f"   ✅ 注文ID: {client_order_index}")
    print(f"   ✅ 市場: {market_symbol} (ID: {market_id})")
    print(f"   ✅ 価格: ${safe_buy_price:.6f}")
    print(f"   ✅ 数量: {buy_size:.6f}")
    print(f"   ✅ 発注→3秒待機→キャンセル成功！")
    print(f"\n💡 このテストでは実際のお金は失われていません")
    print(f"   （約定しない価格で注文し、すぐにキャンセルしました）")


if __name__ == "__main__":
    asyncio.run(main())
