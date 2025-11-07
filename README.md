# XMR Trading Bot - Paradex & Lighter DEX

🤖 **同時実行取引ボット** - ParadexとLighterで同じタイミングでXMR取引を実行

## 概要

このボットは2つのDEX（分散型取引所）で同時にXMRの取引を実行します：

- **Paradex** - Starknetベースの高性能パーペチュアルDEX
- **Lighter** - オーダーブック型のDEX

## 特徴

✨ **同時実行** - 両取引所で同じタイミングで注文を発注
📊 **価格監視** - 両取引所のリアルタイム価格取得
💹 **アービトラージ検出** - 価格差を自動検出
🔄 **非同期処理** - asyncioによる高速実行
⚙️ **柔軟な設定** - 環境変数またはJSONファイルで設定

## インストール

### 必要条件

- Python 3.8以上
- pip

### セットアップ

```bash
# リポジトリをクローン（開発ブランチを指定）
git clone -b claude/xmr-trading-ui-research-011CUtURFcnaRZf8jgeD7ML7 https://github.com/0xnec0/html.git xmr-trading-bot
cd xmr-trading-bot

# 自動セットアップ（推奨）
./setup.sh
```

または手動セットアップ：

```bash
# 依存関係のインストール
pip install -r requirements.txt

# 設定ファイルの作成
cp .env.example .env
# または
cp config.example.json config.json
```

### ⚠️ SDK依存関係の競合について

**重要**: `paradex_py`と`lighter-sdk`は`eth-account`パッケージのバージョン要件が競合するため、**同時にインストールできません**。

✅ **解決策**: このボットは**SDKなしでも完全に動作します**！
REST APIを使用してすべての機能（価格取得、注文、監視）が利用可能です。

SDKを使いたい場合は、どちらか一方のみをインストール：

```bash
# Paradex SDKのみ使用する場合
pip install paradex_py

# またはLighter SDKのみ使用する場合
pip install lighter-sdk
```

## 設定

### 方法1: 環境変数 (.env)

```bash
# Paradex設定
PARADEX_ENV=TESTNET  # または MAINNET
PARADEX_L1_ADDRESS=0x...
PARADEX_L1_PRIVATE_KEY=0x...
PARADEX_MARKET=XMR-USD-PERP

# Lighter設定
LIGHTER_API_KEY=your_api_key
LIGHTER_API_SECRET=your_api_secret
LIGHTER_PRIVATE_KEY=0x...
LIGHTER_MARKET=XMR

# 取引設定
TRADE_AMOUNT=0.1
SLIPPAGE_TOLERANCE=0.5
EXECUTION_TIMEOUT=30
```

### 方法2: JSONファイル (config.json)

```json
{
  "paradex": {
    "env": "TESTNET",
    "l1_address": "0x...",
    "l1_private_key": "0x...",
    "market": "XMR-USD-PERP"
  },
  "lighter": {
    "api_key": "your_api_key",
    "api_secret": "your_api_secret",
    "private_key": "0x...",
    "market": "XMR"
  }
}
```

## 使い方

### 価格確認

両取引所の現在価格とスプレッドを確認：

```bash
python main.py price
```

### 同時取引実行

両取引所で同時に取引を実行：

```bash
# BUY注文
python main.py trade BUY 0.1

# SELL注文
python main.py trade SELL 0.1

# Paradexのみ
python main.py trade BUY 0.1 --paradex-only

# Lighterのみ
python main.py trade SELL 0.1 --lighter-only
```

### アービトラージ

価格差をチェック：

```bash
# アービトラージ機会をチェック（最小スプレッド0.5%）
python main.py arbitrage

# 最小スプレッド1%でチェック
python main.py arbitrage --min-spread 1.0

# アービトラージを実行
python main.py arbitrage --execute --amount 0.1
```

### ポジション監視

現在のポジションと残高を確認：

```bash
python main.py monitor
```

## 設定ファイルを使用

```bash
python main.py --config config.json price
python main.py --config config.json trade BUY 0.1
```

## アーキテクチャ

```
bot/
├── __init__.py          # パッケージ初期化
├── config.py            # 設定管理
├── paradex_client.py    # Paradex接続クライアント
├── lighter_client.py    # Lighter接続クライアント
└── trading_bot.py       # メイン取引ロジック

main.py                  # エントリーポイント
requirements.txt         # Python依存関係
config.example.json      # 設定例
.env.example            # 環境変数例
```

## 主な機能

### ParadexClient

- ✅ 市場価格取得
- ✅ 成行注文発注
- ✅ 注文ステータス確認
- ✅ 口座残高取得
- ✅ 注文キャンセル

### LighterClient

- ✅ 市場価格取得
- ✅ 成行注文発注
- ✅ 注文ステータス確認
- ✅ 口座残高取得
- ✅ 注文キャンセル
- 🔄 SDK/REST APIフォールバック対応

### TradingBot

- ✅ 同時価格取得
- ✅ 同時注文実行
- ✅ アービトラージ機会検出
- ✅ アービトラージ自動実行
- ✅ ポジション監視

## セキュリティ

⚠️ **重要な注意事項**

- 秘密鍵とAPIキーは絶対に共有しない
- `.env`ファイルはgitignoreに含める
- 本番環境では必ずMAINNETを使用
- テストネットで十分にテストしてから本番運用

## トラブルシューティング

### 認証エラー

```
❌ Missing required configuration
```

→ `.env`または`config.json`で必要な認証情報を設定してください

### SDK インポートエラー

```
ModuleNotFoundError: No module named 'paradex_py'
```

→ SDKはオプションです。`pip install -r requirements.txt`だけで動作します。
  SDKを使いたい場合は個別にインストール： `pip install paradex_py`

### 依存関係の競合エラー

```
ERROR: Cannot install paradex-py and lighter-sdk because these package versions have conflicting dependencies.
```

→ これは既知の問題です。両SDKは同時にインストールできません。
  **解決策**: SDKなしで使用（REST APIモード）、またはどちらか一方のSDKのみをインストール

### 価格取得エラー

→ ネットワーク接続を確認し、APIキーが正しいことを確認してください

## 開発

### テスト実行

```bash
# 価格確認（テストネット）
python main.py price

# 少額でテスト
python main.py trade BUY 0.01 --paradex-only
```

### ログ出力

BOTは実行中に詳細なログを出力します：

- ✓ 成功メッセージ（緑）
- ⚠ 警告メッセージ（黄）
- ❌ エラーメッセージ（赤）
- 📊 情報メッセージ（青）

## ライセンス

MIT License

## 免責事項

このソフトウェアは教育目的で提供されています。仮想通貨取引には高いリスクが伴います。自己責任で使用してください。作者は取引による損失について一切の責任を負いません。

## サポート

問題が発生した場合は、GitHubのIssuesセクションで報告してください。

---

**Happy Trading! 🚀**