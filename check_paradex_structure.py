#!/usr/bin/env python3
"""
Paradex SDKの構造を調査
"""
import paradex_py

# paradex_pyのモジュール構造を確認
print("📋 paradex_py モジュール構造:")
print("="*60)

# トップレベル
print("\n1️⃣ paradex_py:")
print([item for item in dir(paradex_py) if not item.startswith('_')])

# common モジュール
try:
    import paradex_py.common as common
    print("\n2️⃣ paradex_py.common:")
    print([item for item in dir(common) if not item.startswith('_')])
except Exception as e:
    print(f"\n❌ paradex_py.common エラー: {e}")

# order モジュール
try:
    import paradex_py.common.order as order
    print("\n3️⃣ paradex_py.common.order:")
    print([item for item in dir(order) if not item.startswith('_')])

    # Orderクラスの確認
    if hasattr(order, 'Order'):
        print("\n✅ Order クラスが見つかりました！")
        print(f"   正しいインポート: from paradex_py.common.order import Order")

    # OrderSide, OrderTypeの確認
    if hasattr(order, 'OrderSide'):
        print(f"   正しいインポート: from paradex_py.common.order import OrderSide")
    if hasattr(order, 'OrderType'):
        print(f"   正しいインポート: from paradex_py.common.order import OrderType")

except Exception as e:
    print(f"\n❌ paradex_py.common.order エラー: {e}")

# その他の可能性を探す
try:
    import paradex_py.api
    print("\n4️⃣ paradex_py.api:")
    print([item for item in dir(paradex_py.api) if not item.startswith('_')])
except Exception as e:
    print(f"\n❌ paradex_py.api エラー: {e}")

print("\n" + "="*60)
