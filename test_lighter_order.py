#!/usr/bin/env python3
"""
Lighter安全注文テスト
目的: 約定しない安全な価格で最小額の注文パラメータを計算

戦略:
- 最良Askより50%高い価格で買い注文（絶対に約定しない）
- 最小サイズ（$20程度）で発注
"""
import os
import asyncio
import aiohttp
from dotenv import load_dotenv
from decimal import Decimal

# 環境変数読み込み
load_dotenv()

async def get_orderbook_details(market_symbol: str):
    """市場の詳細情報を取得"""
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

            print(f"❌ 市場 '{market_symbol}' が見つかりません")
            return None

async def get_orderbook_snapshot(market_id: int):
    """オーダーブックのスナップショットを取得"""
    base_url = os.getenv('LIGHTER_BASE_URL', 'https://mainnet.zklighter.elliot.ai')

    async with aiohttp.ClientSession() as session:
        url = f"{base_url}/api/v1/orderBookOrders?order_book_id={market_id}"

        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status == 200:
                data = await response.json()
                return data
            else:
                print(f"⚠️  オーダーブック取得失敗: HTTP {response.status}")
                return None

def calculate_safe_order_params(market_info: dict, target_usd_value: float = 20.0):
    """
    約定しない安全な注文パラメータを計算

    Args:
        market_info: 市場詳細情報
        target_usd_value: 目標注文金額（USD）

    Returns:
        dict: 注文パラメータ
    """
    symbol = market_info.get('symbol')
    last_price = float(market_info.get('last_trade_price', 0))
    price_decimals = int(market_info.get('price_decimals', 0))
    size_decimals = int(market_info.get('size_decimals', 0))
    min_base_amount = float(market_info.get('min_base_amount', 0))
    min_quote_amount = float(market_info.get('min_quote_amount', 0))
    market_id = market_info.get('market_id')

    if last_price <= 0:
        raise ValueError(f"最終取引価格が無効です: {last_price}")

    print("\n" + "="*60)
    print(f"📊 {symbol} 市場情報")
    print("="*60)
    print(f"Market ID: {market_id}")
    print(f"最終取引価格: ${last_price}")
    print(f"価格精度: {price_decimals} decimals")
    print(f"サイズ精度: {size_decimals} decimals")
    print(f"最小ベース量: {min_base_amount}")
    print(f"最小クオート量: ${min_quote_amount}")

    # 安全な買い注文価格を計算（最終価格の150% = 約定しない）
    safe_buy_price = last_price * 1.5

    # 安全な売り注文価格を計算（最終価格の50% = 約定しない）
    safe_sell_price = last_price * 0.5

    # 目標金額で買える数量を計算
    buy_size = target_usd_value / safe_buy_price

    # 最小数量チェック
    if min_base_amount > 0 and buy_size < min_base_amount:
        print(f"\n⚠️  計算されたサイズ {buy_size} が最小ベース量 {min_base_amount} より小さい")
        buy_size = min_base_amount
        actual_usd_value = buy_size * safe_buy_price
        print(f"   → 最小サイズに調整: {buy_size} (約${actual_usd_value:.2f})")

    # 整数変換（Lighter APIは整数を要求）
    safe_buy_price_int = int(safe_buy_price * (10 ** price_decimals))
    safe_sell_price_int = int(safe_sell_price * (10 ** price_decimals))
    buy_size_int = int(buy_size * (10 ** size_decimals))

    print("\n" + "="*60)
    print("🎯 安全な注文パラメータ（約定しない価格）")
    print("="*60)

    print(f"\n📈 買い注文（BUY）:")
    print(f"   価格: ${safe_buy_price:.6f} (150% of last price)")
    print(f"   価格(整数): {safe_buy_price_int}")
    print(f"   数量: {buy_size:.6f}")
    print(f"   数量(整数): {buy_size_int}")
    print(f"   合計: 約${buy_size * safe_buy_price:.2f}")
    print(f"   💡 最終価格の150%なので絶対に約定しません！")

    print(f"\n📉 売り注文（SELL）:")
    print(f"   価格: ${safe_sell_price:.6f} (50% of last price)")
    print(f"   価格(整数): {safe_sell_price_int}")
    print(f"   数量: {buy_size:.6f}")
    print(f"   数量(整数): {buy_size_int}")
    print(f"   合計: 約${buy_size * safe_sell_price:.2f}")
    print(f"   💡 最終価格の50%なので絶対に約定しません！")

    return {
        'market_id': market_id,
        'symbol': symbol,
        'last_price': last_price,
        'buy': {
            'price': safe_buy_price,
            'price_int': safe_buy_price_int,
            'size': buy_size,
            'size_int': buy_size_int,
            'total_usd': buy_size * safe_buy_price
        },
        'sell': {
            'price': safe_sell_price,
            'price_int': safe_sell_price_int,
            'size': buy_size,
            'size_int': buy_size_int,
            'total_usd': buy_size * safe_sell_price
        },
        'decimals': {
            'price': price_decimals,
            'size': size_decimals
        }
    }

async def main():
    """メイン処理"""
    print("="*60)
    print("🧪 Lighter 安全注文パラメータ計算")
    print("="*60 + "\n")

    # テスト市場（変更可能）
    market_symbol = os.getenv('TEST_MARKET', 'TRX')  # TRX, DOGE, ETH, etc.
    target_usd = float(os.getenv('TEST_ORDER_SIZE_USD', '20.0'))

    print(f"1️⃣ 市場: {market_symbol}")
    print(f"2️⃣ 目標注文金額: ${target_usd}\n")

    # 市場情報取得
    print("3️⃣ 市場情報取得中...")
    market_info = await get_orderbook_details(market_symbol)

    if not market_info:
        print(f"\n❌ 市場 '{market_symbol}' の情報を取得できませんでした")
        return

    print("   ✅ 市場情報取得成功\n")

    # 安全な注文パラメータを計算
    print("4️⃣ 安全な注文パラメータ計算中...")
    order_params = calculate_safe_order_params(market_info, target_usd)

    # オーダーブックスナップショット取得（オプション）
    print("\n5️⃣ 現在のオーダーブック取得中...")
    market_id = market_info.get('market_id')
    orderbook = await get_orderbook_snapshot(market_id)

    if orderbook:
        print("   ✅ オーダーブック取得成功")

        # Bids/Asksの数を表示
        if isinstance(orderbook, dict):
            bids = orderbook.get('bids', [])
            asks = orderbook.get('asks', [])

            if 'data' in orderbook:
                data = orderbook['data']
                bids = data.get('bids', [])
                asks = data.get('asks', [])

            print(f"   現在のBids: {len(bids) if isinstance(bids, list) else 'N/A'}")
            print(f"   現在のAsks: {len(asks) if isinstance(asks, list) else 'N/A'}")

            # 最良bid/askを表示（もしあれば）
            if isinstance(bids, list) and len(bids) > 0:
                best_bid = bids[0] if isinstance(bids[0], (int, float)) else bids[0].get('price', 'N/A')
                print(f"   最良Bid: {best_bid}")

            if isinstance(asks, list) and len(asks) > 0:
                best_ask = asks[0] if isinstance(asks[0], (int, float)) else asks[0].get('price', 'N/A')
                print(f"   最良Ask: {best_ask}")

    print("\n" + "="*60)
    print("✅ 計算完了！")
    print("="*60)

    print("\n📝 次のステップ:")
    print("   1. 上記のパラメータでLighter UIから手動で注文を出す")
    print("   2. または、REST API実装後に自動注文")
    print(f"\n💡 ヒント: .envで TEST_MARKET と TEST_ORDER_SIZE_USD を変更できます")
    print(f"   現在: TEST_MARKET={market_symbol}, TEST_ORDER_SIZE_USD={target_usd}")

if __name__ == "__main__":
    asyncio.run(main())
