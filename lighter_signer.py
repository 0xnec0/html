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

    # Time In Force定数（lighter-python準拠）
    ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL = 0  # IOC - 即時実行またはキャンセル
    ORDER_TIME_IN_FORCE_GOOD_TILL_TIME = 1       # GTT - 期限まで有効
    ORDER_TIME_IN_FORCE_POST_ONLY = 2            # Post-only (maker注文)

    # トランザクションタイプ定数
    TX_TYPE_CREATE_ORDER = 14
    TX_TYPE_CANCEL_ORDER = 15

    # デフォルト有効期限
    DEFAULT_28_DAY_ORDER_EXPIRY = 28 * 24 * 60 * 60  # 28日（秒）
    DEFAULT_10_MIN_AUTH_EXPIRY = 10 * 60  # 10分（秒）

    def __init__(self, private_key: str, account_index: int, api_key_index: int = 2):
        """
        初期化

        Args:
            private_key: Lighter秘密鍵（0xなし64文字）
            account_index: アカウントインデックス
            api_key_index: APIキーインデックス（デフォルト2、lighter-python準拠）
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

        # CreateClient関数（lighter-pythonの正しい方法）
        self.signer.CreateClient.argtypes = [
            ctypes.c_char_p,    # url
            ctypes.c_char_p,    # private_key
            ctypes.c_int,       # chain_id
            ctypes.c_int,       # api_key_index
            ctypes.c_longlong,  # account_index（c_intではなくc_longlong！）
        ]
        self.signer.CreateClient.restype = ctypes.c_char_p  # エラー文字列またはNone

        # クライアント作成（秘密鍵で初期化）
        # Lighter mainnet: chain_id = 304（lighter-python標準）
        base_url = "https://mainnet.zklighter.elliot.ai"
        chain_id = 304  # mainnet

        err = self.signer.CreateClient(
            base_url.encode('utf-8'),
            self.private_key.encode('utf-8'),
            chain_id,
            self.api_key_index,
            self.account_index
        )

        # Noneなら成功、それ以外はエラー
        if err is not None:
            err_str = err.decode('utf-8')
            raise RuntimeError(f"Signer initialization failed: {err_str}")

        print(f"✓ Signer initialized for account {self.account_index}")

        # StrOrErr構造体の定義（他の署名関数用）
        class StrOrErr(ctypes.Structure):
            _fields_ = [
                ("result", ctypes.c_char_p),
                ("error", ctypes.c_char_p),
            ]

        self.StrOrErr = StrOrErr

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
            # time_in_forceに応じたorder_expiry設定
            # GOOD_TILL_TIME (Limit Order): -1 = バイナリ側で自動28日設定
            # IMMEDIATE_OR_CANCEL (Market): 0
            # デフォルトはLimit Order用
            order_expiry = -1

        # デバッグ: 実際の値を確認
        current_time = int(time.time())
        print(f"[DEBUG] 現在時刻: {current_time}")
        print(f"[DEBUG] order_expiry: {order_expiry}")
        if order_expiry == -1:
            print(f"[DEBUG] 有効期限: 自動28日設定")
        elif order_expiry == 0:
            print(f"[DEBUG] 有効期限: IOC（即時実行またはキャンセル）")
        else:
            print(f"[DEBUG] 差分: {order_expiry - current_time}秒")

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
                # デバッグ: 署名されたトランザクションJSONを表示
                print(f"[DEBUG] 署名されたトランザクションJSON:")
                print(tx_json)
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


def get_proxy_url() -> Optional[str]:
    """
    環境変数からプロキシURLを構築

    Returns:
        プロキシURL（無効の場合None）
    """
    import os
    from dotenv import load_dotenv
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


async def get_next_nonce(base_url: str, account_index: int, api_key_index: int) -> int:
    """
    Lighter APIから次のnonceを取得

    Args:
        base_url: Lighter API URL
        account_index: アカウントインデックス
        api_key_index: APIキーインデックス

    Returns:
        次のnonce値
    """
    import aiohttp

    url = f"{base_url}/api/v1/nextNonce"
    params = {
        'account_index': account_index,
        'api_key_index': api_key_index
    }

    proxy_url = get_proxy_url()

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, proxy=proxy_url) as response:
            if response.status == 200:
                data = await response.json()
                return data['nonce']
            else:
                text = await response.text()
                raise Exception(f"Failed to get nonce - HTTP {response.status}: {text}")


async def send_transaction(base_url: str, tx_json: str, tx_type: int) -> dict:
    """
    署名済みトランザクションをLighter APIに送信

    Args:
        base_url: Lighter API URL
        tx_json: 署名済みトランザクションJSON文字列
        tx_type: トランザクションタイプ（14=CREATE_ORDER, 15=CANCEL_ORDER）

    Returns:
        APIレスポンス
    """
    import aiohttp

    url = f"{base_url}/api/v1/sendTx"

    # multipart/form-dataとして送信
    form_data = aiohttp.FormData()
    form_data.add_field('tx_type', str(tx_type))
    form_data.add_field('tx_info', tx_json)

    proxy_url = get_proxy_url()

    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=form_data, proxy=proxy_url) as response:
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
