# Paradex & Lighter 両建てボット

🚀 **超シンプル・堅牢な両建てボット** - Paradex & Lighterで安定した接続テスト

---

## 📋 概要

このプロジェクトは、**Paradex**と**Lighter**の2つの取引所で両建て取引を行うボットの基盤です。
まずは**API接続の安定性を確認**することに集中しています。

### 🎯 現在の機能

- ✅ **Paradex Mainnet接続テスト** - アカウント情報・市場価格取得
- ✅ **Lighter Mainnet接続テスト** - アカウント情報・市場情報取得
- ✅ **Lighter WebSocket監視** - 注文約定イベントのリアルタイム受信

---

## 🚀 セットアップ

### 1. リポジトリクローン

```bash
git clone <your-repo-url>
cd paradex-lighter-bot
```

### 2. Python仮想環境作成

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# または
venv\Scripts\activate  # Windows
```

### 3. 依存関係インストール

```bash
pip install -r requirements.txt
```

**インストールされるもの:**
- `paradex_py` - Paradex公式Python SDK
- `lighter-python` - Lighter公式Python SDK
- `python-dotenv` - 環境変数管理
- `websockets` - WebSocket通信
- `aiohttp` - 非同期HTTP通信

### 4. 環境変数設定

```bash
cp .env.example .env
nano .env  # または vim, code など好きなエディタで編集
```

**必須の環境変数:**

```bash
# Paradex
PARADEX_ENV=prod
PARADEX_L1_PRIVATE_KEY=0x...  # あなたのEthereum秘密鍵
PARADEX_L1_ADDRESS=0x...      # あなたのEthereumアドレス

# Lighter
LIGHTER_PRIVATE_KEY=0x...     # あなたのLighter API秘密鍵
LIGHTER_ACCOUNT_INDEX=0       # アカウントインデックス
LIGHTER_API_KEY_INDEX=2       # API Keyインデックス（2-254）
```

---

## 📝 使い方

### テスト1: Paradex接続テスト

```bash
python test_paradex.py
```

**期待される出力:**
```
============================================================
🔌 Paradex Mainnet 接続テスト
============================================================

1️⃣ SDK初期化中...
   ✅ SDK初期化成功

2️⃣ アカウント情報取得中...
   ✅ アカウント取得成功
   Account ID: 0x...
   L2 Address: 0x...

3️⃣ 市場一覧取得中...
   ✅ 市場データ取得成功
   利用可能市場数: 20個

   主要市場:
     1. BTC-USD-PERP: $96500.00
     2. ETH-USD-PERP: $3650.00
     3. SOL-USD-PERP: $220.50

============================================================
🎉 Paradex接続テスト完了！全て成功！
============================================================
```

---

### テスト2: Lighter接続テスト

```bash
python test_lighter.py
```

**期待される出力:**
```
============================================================
🔌 Lighter Mainnet 接続テスト
============================================================

0️⃣ Lighter SDK インポート中...
   ✅ SDK インポート成功

1️⃣ SDK初期化中...
   ✅ SDK初期化成功
   Base URL: https://mainnet.zklighter.elliot.ai

2️⃣ アカウント情報取得中...
   ✅ アカウント取得成功
   Account Index: 0

3️⃣ 市場情報取得中...
   ✅ 市場データ取得成功
   利用可能市場数: 15個

   主要市場:
     1. Market 0: BTC-PERP
     2. Market 1: ETH-PERP
     3. Market 2: SOL-PERP

============================================================
🎉 Lighter接続テスト完了！
============================================================
```

---

### テスト3: Lighter WebSocket監視

```bash
python test_lighter_websocket.py
```

**使い方:**
1. 別のターミナルでLighterに小額の指値注文を出す
2. このスクリプトを実行
3. 注文が約定するとWebSocketイベントを受信

**期待される出力:**
```
============================================================
🔌 Lighter WebSocket 接続テスト
============================================================

1️⃣ SDK初期化中...
   ✅ SDK初期化成功

2️⃣ WebSocket接続準備中...
   ✅ コールバック準備完了

3️⃣ WebSocket購読開始...
   ✅ WebSocket購読成功

4️⃣ イベント監視中（60秒間）...
   💡 この間に注文が約定すればイベントが届きます
   💡 Ctrl+C で中断できます

   ⏱️  10秒経過... (受信イベント数: 0)

📨 【イベント 1】アカウント更新受信:
   タイムスタンプ: 1699999999
   ポジション数: 1
     - Market: 3, Size: 0.1

   📊 監視終了: 合計 1 件のイベントを受信

============================================================
🎉 WebSocketテスト完了！
============================================================
```

---

## 🔧 トラブルシューティング

### エラー: `ModuleNotFoundError: No module named 'lighter'`

**原因:** Lighter SDKがインストールされていない

**解決策:**
```bash
pip install git+https://github.com/elliottech/lighter-python.git@main
```

---

### エラー: `Authentication failed`

**原因:** 環境変数の秘密鍵が正しくない

**解決策:**
1. `.env`ファイルの秘密鍵を確認
2. `0x`プレフィックスが付いているか確認
3. 秘密鍵が正しいウォレットのものか確認

---

### エラー: `WebSocket connection failed`

**原因:** Lighter WebSocketサーバーに接続できない

**解決策:**
1. インターネット接続を確認
2. ファイアウォール設定を確認
3. しばらく待ってから再試行

---

## 📚 次のステップ

現在は**接続テストのみ**ですが、今後以下の機能を追加予定：

### Phase 1: 基本機能
- [ ] 価格取得機能
- [ ] 注文機能（成行・指値）
- [ ] ポジション管理

### Phase 2: 両建て戦略
- [ ] Lighter指値注文 → Paradex成行ヘッジ
- [ ] WebSocket約定検知 → 即座にヘッジ
- [ ] ポジション自動決済

### Phase 3: 高度な機能
- [ ] ファンディングレートアービトラージ
- [ ] スプレッド監視
- [ ] P&L計算
- [ ] Proxy対応

---

## 🔒 セキュリティ

⚠️ **重要な注意事項**

- 秘密鍵とAPIキーは絶対に共有しない
- `.env`ファイルは`.gitignore`に含まれています（コミットされません）
- **まず小額でテスト**してから本番運用してください
- Mainnetを使用していますが、最初は最小金額で動作確認を！

---

## 📄 ライセンス

MIT License

---

## 💬 サポート

問題が発生した場合は、GitHubのIssuesセクションで報告してください。

---

**Happy Trading! 🚀**
