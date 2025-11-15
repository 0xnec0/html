# プロキシ設定ガイド

## 概要

LighterとParadex両方の取引所APIがプロキシ経由で動作するように実装しました。
レジデンシャルプロキシに対応しています。

## 設定方法

### 1. .envファイルにプロキシ情報を追加

`.env`ファイルに以下の設定を追加してください：

```bash
# ========================================
# Proxy Configuration
# ========================================
PROXY_ENABLED=true
PROXY_SERVER=as.smartproxy.net
PROXY_PORT=3120
PROXY_USERNAME=smart-q2lwm7pfe5i3
PROXY_PASSWORD=us1YRmGVF1WKNnnb
```

### 2. プロキシを無効にする場合

プロキシを使わずに直接接続したい場合は：

```bash
PROXY_ENABLED=false
```

または、PROXY_ENABLED行をコメントアウト：

```bash
# PROXY_ENABLED=true
```

## 実装詳細

### Lighter API

- `lighter_signer.py`の`get_next_nonce()`と`send_transaction()`関数がプロキシに対応
- aiohttpの標準proxy引数を使用
- 認証情報はURL形式で渡される: `http://username:password@server:port`

### Paradex API

- `paradex_client.py`ヘルパーモジュールを使用
- HTTP_PROXY/HTTPS_PROXY環境変数を設定
- Paradex SDKが内部で使用するHTTPクライアントが自動的にプロキシを認識

## テスト方法

### プロキシ接続テスト

両取引所のAPIがプロキシ経由で正常に動作するか確認：

```bash
python test_proxy_connection.py
```

このスクリプトは以下をテストします：

1. **Lighter API**
   - Signer初期化
   - Nonce取得（API接続）
   - 市場情報取得

2. **Paradex API**
   - クライアント初期化
   - 市場情報取得
   - アカウント残高取得

### 既存スクリプトでのプロキシ使用

すべての既存スクリプトがプロキシに対応済み：

```bash
# Paradex接続テスト（プロキシ経由）
python test_paradex.py

# Lighter注文テスト（プロキシ経由）
python test_lighter_order_cancel.py

# Paradex成行注文テスト（プロキシ経由）
python test_paradex_order.py
```

## トラブルシューティング

### プロキシ認証エラー

```
HTTP 407 Proxy Authentication Required
```

→ PROXY_USERNAME と PROXY_PASSWORD を確認してください

### プロキシ接続タイムアウト

```
Cannot connect to proxy
```

→ PROXY_SERVER と PROXY_PORT が正しいか確認してください
→ プロキシサービスが稼働中か確認してください

### プロキシを経由しているか確認

test_proxy_connection.pyを実行すると、プロキシ設定が表示されます：

```
✓ プロキシ有効: as.smartproxy.net:3120
```

この表示が出ていれば、プロキシ経由でリクエストが送信されています。

## セキュリティ注意事項

- `.env`ファイルはGitにコミットしないでください（`.gitignore`に追加済み）
- プロキシ認証情報を他人と共有しないでください
- 本番環境では環境変数や秘密管理サービスを使用してください

## 次のステップ

プロキシ接続が確認できたら、グリッドボットの開発に進みます：

1. グリッドボットのパラメータ設計
2. グリッド注文配置ロジック実装
3. 注文約定検知とリバランス
4. 少額でのライブテスト

---

**実装完了！** 🎉

両取引所がプロキシ経由で正常に動作します。
