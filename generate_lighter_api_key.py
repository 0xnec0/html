#!/usr/bin/env python3
"""
Lighter APIキー生成ツール

Lighter専用のAPIキー（40バイト）を生成します。
これはEthereumの秘密鍵（32バイト）とは異なります。

使い方:
1. このスクリプトを実行してAPIキーを生成
2. 生成されたPublic Keyを使ってLighterにAPIキーを登録
3. 生成されたPrivate Keyを.envファイルに保存
"""
import ctypes
import os

class ApiKeyResponse(ctypes.Structure):
    """APIキー生成のレスポンス構造体"""
    _fields_ = [
        ("privateKey", ctypes.c_char_p),
        ("publicKey", ctypes.c_char_p),
        ("err", ctypes.c_char_p),
    ]

def generate_lighter_api_key(seed=""):
    """
    Lighter専用のAPIキーを生成

    Args:
        seed: シード文字列（空の場合はランダム生成）

    Returns:
        (private_key, public_key, error)
    """
    # 署名ライブラリロード
    current_dir = os.path.dirname(os.path.abspath(__file__))
    signer_path = os.path.join(current_dir, "lighter_signer", "signer-amd64.so")

    if not os.path.exists(signer_path):
        raise FileNotFoundError(f"Lighter signer binary not found: {signer_path}")

    signer = ctypes.CDLL(signer_path)

    # GenerateAPIKey関数の設定
    signer.GenerateAPIKey.argtypes = [ctypes.c_char_p]
    signer.GenerateAPIKey.restype = ApiKeyResponse

    # APIキー生成
    result = signer.GenerateAPIKey(seed.encode('utf-8') if seed else b"")

    if result.err:
        return None, None, result.err.decode('utf-8')

    private_key = result.privateKey.decode('utf-8') if result.privateKey else None
    public_key = result.publicKey.decode('utf-8') if result.publicKey else None

    # 0xプレフィックスを削除
    if private_key and private_key.startswith('0x'):
        private_key = private_key[2:]
    if public_key and public_key.startswith('0x'):
        public_key = public_key[2:]

    return private_key, public_key, None

if __name__ == "__main__":
    print("="*60)
    print("🔑 Lighter APIキー生成ツール")
    print("="*60)
    print()

    print("📌 重要な情報:")
    print("   Lighterは独自の暗号方式を使用しています：")
    print("   - 楕円曲線: Goldilocks (ECgFp5)")
    print("   - 署名方式: Schnorr")
    print("   - 秘密鍵長: 40バイト (80 hex文字)")
    print()
    print("   ⚠️ これはEthereumの秘密鍵（32バイト）とは異なります！")
    print()

    # APIキー生成
    print("🔄 APIキーを生成中...")
    private_key, public_key, error = generate_lighter_api_key()

    if error:
        print(f"❌ エラー: {error}")
        exit(1)

    print("✅ APIキー生成成功！\n")

    print("="*60)
    print("📋 生成されたAPIキー")
    print("="*60)
    print()
    print(f"🔐 Private Key (秘密鍵 - 40バイト):")
    print(f"   {private_key}")
    print()
    print(f"🔓 Public Key (公開鍵):")
    print(f"   {public_key}")
    print()

    print("="*60)
    print("📝 次のステップ")
    print("="*60)
    print()
    print("1️⃣ Lighterアカウントに新しいAPIキーを登録:")
    print("   - Lighter WebサイトまたはAPIを使用")
    print(f"   - Public Key: {public_key}")
    print("   - 登録後、api_key_indexを確認してください")
    print()
    print("2️⃣ .envファイルを更新:")
    print("   以下を.envファイルに追加または更新してください：")
    print()
    print(f"   LIGHTER_API_KEY={private_key}")
    print("   LIGHTER_API_KEY_INDEX=<登録時に取得したindex>")
    print()
    print("3️⃣ lighter_signer.pyを更新:")
    print("   - LIGHTER_PRIVATE_KEYの代わりにLIGHTER_API_KEYを使用")
    print("   - APIキーは40バイト（80 hex文字）である必要があります")
    print()
    print("="*60)
    print()
    print("💡 ヒント:")
    print("   - Private Keyは絶対に他人と共有しないでください")
    print("   - .envファイルをgitにコミットしないでください")
    print("   - バックアップを安全な場所に保存してください")
    print()
