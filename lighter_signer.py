#!/usr/bin/env python3
"""
Lighter署名モジュール（lighter-goバイナリ使用）

lighter-sdkの依存関係競合を回避するため、
lighter-goの共有ライブラリを直接ctypesで呼び出す。
"""
import os
import ctypes
import json
import time
from typing import Optional, Tuple

class LighterSigner:
    """Lighter注文署名クラス"""

    # 注文タイプ定数
    ORDER_TYPE_LIMIT = 0
    ORDER_TYPE_MARKET = 1
    ORDER_TYPE_STOP_LOSS = 2
    ORDER_TYPE_TAKE_PROFIT = 3

    # Time In Force定数
    ORDER_TIME_IN_FORCE_GOOD_TILL_TIME = 0
    ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL = 1
    ORDER_TIME_IN_FORCE_FILL_OR_KILL = 2

    # デフォルト有効期限
    DEFAULT_28_DAY_ORDER_EXPIRY = 28 * 24 * 60 * 60  # 28日（秒）
    DEFAULT_10_MIN_AUTH_EXPIRY = 10 * 60  # 10分（秒）

    def __init__(self, private_key: str, account_index: int, api_key_index: int = 255):
        """
        初期化

        Args:
            private_key: Lighter秘密鍵（0xなし64文字）
            account_index: アカウントインデックス
            api_key_index: APIキーインデックス（デフォルト255）
        """
        # 0xプレフィックス削除
        if private_key.startswith('0x') or private_key.startswith('0X'):
            private_key = private_key[2:]

        self.private_key = private_key
        self.account_index = account_index
        self.api_key_index = api_key_index

        # 署名ライブラリロード
        current_dir = os.path.dirname(os.path.abspath(__file__))
        signer_path = os.path.join(current_dir, "lighter_signer", "signer-amd64.so")

        if not os.path.exists(signer_path):
            raise FileNotFoundError(f"Lighter signer binary not found: {signer_path}")

        try:
            self.signer = ctypes.CDLL(signer_path)
            print(f"✓ Lighter signer loaded: {signer_path}")
        except Exception as e:
            raise RuntimeError(f"Failed to load Lighter signer: {e}")

        # 署名関数の準備
        self._setup_functions()

    def _setup_functions(self):
        """ctypes関数シグネチャ設定"""

        # StrOrErr構造体の定義（戻り値用）
        class StrOrErr(ctypes.Structure):
            _fields_ = [
                ("result", ctypes.c_char_p),
                ("error", ctypes.c_char_p),
            ]

        self.StrOrErr = StrOrErr

        # Initialize関数
        self.signer.Initialize.argtypes = [ctypes.c_char_p]
        self.signer.Initialize.restype = StrOrErr

        # 秘密鍵で初期化
        result = self.signer.Initialize(self.private_key.encode('utf-8'))
        if result.error:
            raise RuntimeError(f"Signer initialization failed: {result.error.decode('utf-8')}")

        print(f"✓ Signer initialized for account {self.account_index}")

        # SignCreateOrder関数
        self.signer.SignCreateOrder.argtypes = [
            ctypes.c_int,       # market_index
            ctypes.c_longlong,  # client_order_index
            ctypes.c_longlong,  # base_amount
            ctypes.c_int,       # price
            ctypes.c_int,       # is_ask (0=buy, 1=sell)
            ctypes.c_int,       # order_type
            ctypes.c_int,       # time_in_force
            ctypes.c_int,       # reduce_only
            ctypes.c_int,       # trigger_price
            ctypes.c_longlong,  # order_expiry
            ctypes.c_longlong,  # nonce (-1で自動)
        ]
        self.signer.SignCreateOrder.restype = StrOrErr

        # SignCancelOrder関数
        self.signer.SignCancelOrder.argtypes = [
            ctypes.c_int,       # market_index
            ctypes.c_longlong,  # order_index
            ctypes.c_longlong,  # nonce (-1で自動)
        ]
        self.signer.SignCancelOrder.restype = StrOrErr

    def sign_create_order(
        self,
        market_index: int,
        client_order_index: int,
        base_amount: int,
        price: int,
        is_ask: bool,
        order_type: int = ORDER_TYPE_LIMIT,
        time_in_force: int = ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
        reduce_only: bool = False,
        trigger_price: int = 0,
        order_expiry: int = None,
        nonce: int = -1
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        注文作成トランザクションに署名

        Args:
            market_index: 市場インデックス
            client_order_index: クライアント注文インデックス（ユニーク）
            base_amount: 数量（整数）
            price: 価格（整数）
            is_ask: True=売り、False=買い
            order_type: 注文タイプ
            time_in_force: 有効期限タイプ
            reduce_only: True=ポジション縮小のみ
            trigger_price: トリガー価格（0=なし）
            order_expiry: 注文有効期限（秒、Noneでデフォルト28日）
            nonce: ノンス（-1で自動）

        Returns:
            (署名済みトランザクションJSON, エラーメッセージ)
        """
        if order_expiry is None:
            order_expiry = int(time.time()) + self.DEFAULT_28_DAY_ORDER_EXPIRY

        try:
            result = self.signer.SignCreateOrder(
                market_index,
                client_order_index,
                base_amount,
                price,
                int(is_ask),
                order_type,
                time_in_force,
                int(reduce_only),
                trigger_price,
                order_expiry,
                nonce
            )

            if result.error:
                error_msg = result.error.decode('utf-8')
                return None, error_msg

            if result.result:
                tx_json = result.result.decode('utf-8')
                return tx_json, None

            return None, "No result returned"

        except Exception as e:
            return None, str(e)

    def sign_cancel_order(
        self,
        market_index: int,
        order_index: int,
        nonce: int = -1
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        注文キャンセルトランザクションに署名

        Args:
            market_index: 市場インデックス
            order_index: 注文インデックス（client_order_indexと同じ）
            nonce: ノンス（-1で自動）

        Returns:
            (署名済みトランザクションJSON, エラーメッセージ)
        """
        try:
            result = self.signer.SignCancelOrder(
                market_index,
                order_index,
                nonce
            )

            if result.error:
                error_msg = result.error.decode('utf-8')
                return None, error_msg

            if result.result:
                tx_json = result.result.decode('utf-8')
                return tx_json, None

            return None, "No result returned"

        except Exception as e:
            return None, str(e)


async def send_transaction(base_url: str, tx_json: str) -> dict:
    """
    署名済みトランザクションをLighter APIに送信

    Args:
        base_url: Lighter API URL
        tx_json: 署名済みトランザクションJSON文字列

    Returns:
        APIレスポンス
    """
    import aiohttp

    url = f"{base_url}/api/v1/sendTx"

    # JSON文字列をパース
    tx_data = json.loads(tx_json)

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=tx_data) as response:
            if response.status == 200:
                return await response.json()
            else:
                text = await response.text()
                raise Exception(f"HTTP {response.status}: {text}")


if __name__ == "__main__":
    # 簡単なテスト
    print("Lighter Signer Module Test")
    print("=" * 60)

    # 環境変数から秘密鍵取得
    import os
    from dotenv import load_dotenv
    load_dotenv()

    private_key = os.getenv('LIGHTER_PRIVATE_KEY')
    account_index = int(os.getenv('LIGHTER_ACCOUNT_INDEX', '0'))

    if not private_key:
        print("❌ LIGHTER_PRIVATE_KEY not set in .env")
    else:
        try:
            signer = LighterSigner(
                private_key=private_key,
                account_index=account_index,
                api_key_index=255
            )
            print("✅ Signer initialized successfully!")
            print(f"   Account Index: {account_index}")

        except Exception as e:
            print(f"❌ Error: {e}")
