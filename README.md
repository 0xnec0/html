# Multi-DEX Trading Bot - Paradex & Lighter

🤖 **同時実行取引ボット** - ParadexとLighterで同じタイミングで取引を実行

## 概要

このボットは2つのDEX（分散型取引所）で同時に取引を実行します：

- **Paradex** - Starknetベースの高性能パーペチュアルDEX
- **Lighter** - オーダーブック型のDEX

## 特徴

✨ **同時実行** - 両取引所で同じタイミングで注文を発注
📊 **価格監視** - 両取引所のリアルタイム価格取得
💹 **アービトラージ検出** - 価格差を自動検出
💰 **デルタニュートラル戦略** - ヘッジポジションで安定収益を狙う
🔄 **非同期処理** - asyncioによる高速実行
⚙️ **柔軟な設定** - 環境変数またはJSONファイルで設定
🤖 **自動ループ** - ポジションの自動ローテーション

## インストール

### 必要条件

- Python 3.8以上
- pip

### セットアップ

#### 🚀 クイックスタート（推奨）

```bash
# リポジトリをクローン
git clone -b claude/xmr-trading-ui-research-011CUtsNpvMhrKApzi7s9mR4 \
  https://github.com/0xnec0/html.git doge-trading-bot
cd doge-trading-bot

# 自動セットアップ（仮想環境も自動作成）
./quickstart.sh

# 仮想環境をアクティベート（将来のセッションで必要）
source venv/bin/activate

# 設定ファイルを作成
cp .env.example .env
nano .env  # 認証情報を記入
```

#### 📋 手動セットアップ

Debian/Ubuntu系システムでは仮想環境が必要です：

```bash
# 1. 仮想環境を作成
python3 -m venv venv

# 2. 仮想環境をアクティベート
source venv/bin/activate

# 3. 依存関係のインストール
pip install -r requirements.txt

# 4. 設定ファイルの作成
cp .env.example .env
# または
cp config.example.json config.json
```

**注意:** 仮想環境を使わずにシステム全体にインストールする場合：
```bash
# 非推奨：システムパッケージを破壊する可能性があります
pip3 install -r requirements.txt --break-system-packages
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
PARADEX_MARKET=DOGE-USD-PERP

# Lighter設定
LIGHTER_API_KEY=your_api_key
LIGHTER_API_SECRET=your_api_secret
LIGHTER_PRIVATE_KEY=0x...
LIGHTER_MARKET=DOGE

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
    "market": "DOGE-USD-PERP"
  },
  "lighter": {
    "api_key": "your_api_key",
    "api_secret": "your_api_secret",
    "private_key": "0x...",
    "market": "DOGE"
  }
}
```

## 使い方

### 🔌 接続テスト（重要！）

まず最初に、取引所への接続が正常か確認しましょう：

```bash
python main.py test
```

このコマンドは：
- ✅ Paradexへの接続確認
- ✅ Lighterへの接続確認
- ✅ アカウント情報の表示
- ✅ 残高情報の表示（利用可能な場合）

**取引を始める前に必ず実行してください！**

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

### 🔄 自動取引ループ（NEW!）

ポジションを持って2-3時間の間でランダムにポジションを決済し、ループします：

```bash
# 基本的な使い方（デフォルト: 2-3時間）
python main.py autoloop BUY 0.1

# ホールド時間をカスタマイズ（1-2時間）
python main.py autoloop BUY 0.1 --min-hours 1.0 --max-hours 2.0

# 最大繰り返し回数を指定（10回で停止）
python main.py autoloop BUY 0.1 --max-iterations 10

# Paradexのみで自動取引
python main.py autoloop SELL 0.1 --paradex-only

# 完全なカスタマイズ例
python main.py autoloop BUY 0.05 --min-hours 2.5 --max-hours 4.0 --max-iterations 5
```

**動作：**
1. 指定した方向（BUY/SELL）でポジションをオープン
2. ランダムな時間（2-3時間の間）待機
3. ポジションをクローズ（反対売買）
4. 1に戻る（次は反対方向でオープン）

**Ctrl+C**で安全に停止できます。

### 💰 デルタニュートラル戦略（NEW!）

**Paradexでロング（買い）+ Lighterでショート（売り）** を同時に持つことで、価格変動リスクを相殺しながらファンディングレートで利益を狙う戦略です。

```bash
# 基本的な使い方（.envの設定を使用）
python main.py delta-neutral

# USD金額を指定（50ドル分のポジション）
python main.py delta-neutral --usd-amount 50

# ホールド時間をカスタマイズ（3-6分でテスト）
python main.py delta-neutral --usd-amount 50 --min-hours 0.05 --max-hours 0.1

# 最大サイクル数を指定（5回で停止）
python main.py delta-neutral --usd-amount 100 --max-cycles 5

# 完全なカスタマイズ例
python main.py delta-neutral \
  --usd-amount 50 \
  --leverage 10 \
  --min-hours 2.0 \
  --max-hours 3.0 \
  --max-cycles 10
```

**動作：**
1. Paradexでロング（BUY）+ Lighterでショート（SELL）を同時オープン
2. ランダムな時間（2-3時間デフォルト）待機
3. 両ポジションをクローズ（Paradex SELL + Lighter BUY）
4. 30秒待機して1に戻る

**.envで設定（推奨）:**
```bash
# デルタニュートラル戦略設定
DELTA_NEUTRAL_USD_AMOUNT=50      # 1ポジションあたりのUSD金額
DELTA_NEUTRAL_LEVERAGE=10        # レバレッジ倍率
DELTA_NEUTRAL_CAPITAL_PCT=0.5    # 証拠金の使用率（50%）
DELTA_NEUTRAL_MIN_HOURS=2.0      # 最小保持時間
DELTA_NEUTRAL_MAX_HOURS=3.0      # 最大保持時間

# スプレッド監視設定（NEW!）
SPREAD_MAX_PCT=0.02              # 最大許容スプレッド（%）- ポジションを開く前に必須
SPREAD_CHECK_INTERVAL=2          # チェック間隔（秒）
SPREAD_CHECK_TIMEOUT=0           # タイムアウト（秒）- 0=無限待機
```

**スプレッド監視機能（NEW!）:**
- 🎯 取引所間のスプレッドが0.02%以下になるまで待機
- 🔄 リアルタイムで価格とスプレッドを監視・表示
- ⏱️ タイムアウト設定可能（0=条件達成まで無限待機）
- 💰 より正確なヘッジでコストを最小化

**メリット：**
- ✅ 価格変動リスクがほぼゼロ（ヘッジ済み）
- ✅ ファンディングレートで安定収益
- ✅ 自動的にポジションローテーション
- ✅ 両取引所で同じUSD金額のポジション
- ✅ 片方失敗時の自動クリーンアップ機能

**安全機能：**
- 🛡️ スプレッド監視でより正確なヘッジ価格を確保
- 🛡️ 片方の取引所でポジションオープンに失敗した場合、もう片方も自動的にクローズ
- 🛡️ ヘッジされていない危険な状態を自動的に回避
- 🛡️ 失敗時は詳細なエラーメッセージを表示

**リスク：**
- ⚠️ 極端な価格変動時の清算リスク
- ⚠️ ファンディングレートが逆転する可能性
- ⚠️ スプレッドコスト
- ⚠️ 両取引所の同時接続が必要

**Ctrl+C**で安全に停止できます。

### 🛑 緊急停止 - 全ポジションクローズ

デルタニュートラル戦略やその他の取引で開いたポジションを緊急で決済したい場合：

```bash
# 自動検出（デルタニュートラル戦略のポジション情報を使用）
python main.py close-all

# サイズを手動指定
python main.py close-all --size 156

# Paradexのポジションのみ決済
python main.py close-all --paradex-only

# Lighterのポジションのみ決済
python main.py close-all --lighter-only
```

**動作：**
- デルタニュートラル戦略が保存したポジション情報を自動読み込み
- Paradex: SELL注文（ロングポジションをクローズ）
- Lighter: BUY注文（ショートポジションをクローズ）
- 両注文を同時実行

**自動検出の仕組み：**
- デルタニュートラル戦略がポジションを開くと `.current_position.json` に情報を保存
- `close-all` コマンドは自動的にこのファイルを読み込む
- ポジションを閉じると自動的にファイルを削除

**使用例：**
```bash
# デルタニュートラル戦略実行中
python main.py delta-neutral --usd-amount 50

# 別のターミナルから緊急停止（サイズ自動検出）
python main.py close-all
```

**注意：**
- デルタニュートラル戦略以外のポジションは `--size` を手動指定してください
- 自動検出が失敗した場合はエラーメッセージが表示されます

## 設定ファイルを使用

```bash
python main.py --config config.json price
python main.py --config config.json trade BUY 0.1
```

## アーキテクチャ

```
bot/
├── __init__.py               # パッケージ初期化
├── config.py                 # 設定管理
├── paradex_client.py         # Paradex接続クライアント
├── lighter_client.py         # Lighter接続クライアント
├── trading_bot.py            # メイン取引ロジック
├── auto_trader.py            # 自動取引ループ
└── delta_neutral_strategy.py # デルタニュートラル戦略

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

- ✅ 接続テスト（両取引所への接続確認）
- ✅ 同時価格取得
- ✅ 同時注文実行
- ✅ アービトラージ機会検出
- ✅ アービトラージ自動実行
- ✅ ポジション監視

### AutoTrader（自動取引ループ）

- ✅ ランダムなホールド時間（2-3時間デフォルト）
- ✅ 自動的にポジションのオープン/クローズ
- ✅ 安全な停止機能（Ctrl+C）
- ✅ 進捗表示とログ出力
- ✅ カスタマイズ可能な繰り返し回数

### DeltaNeutralStrategy（デルタニュートラル戦略）

- ✅ 両取引所で同時ヘッジポジション（Paradex LONG + Lighter SHORT）
- ✅ USD金額指定でポジションサイズ自動計算
- ✅ 両取引所で均等なUSD金額のポジション
- ✅ レバレッジ対応（デフォルト10x）
- ✅ 自動的なポジションローテーション
- ✅ P&L（損益）計算と表示
- ✅ 安全な停止機能（Ctrl+C）
- ✅ .envファイルで設定可能
- ✅ 片方失敗時の自動クリーンアップ（危険な片側ポジションを自動決済）

## セキュリティ

⚠️ **重要な注意事項**

- 秘密鍵とAPIキーは絶対に共有しない
- `.env`ファイルはgitignoreに含める
- 本番環境では必ずMAINNETを使用
- テストネットで十分にテストしてから本番運用

## トラブルシューティング

### pip インストールエラー（externally-managed-environment）

```
error: externally-managed-environment
```

**原因:** Debian/Ubuntu 22.04+のPython 3.11+では、システムPythonパッケージの保護のため直接pipインストールが制限されています。

**解決策1:** 仮想環境を使用（推奨）
```bash
# クイックスタートスクリプトを使用
./quickstart.sh

# または手動で仮想環境作成
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**解決策2:** システム全体にインストール（非推奨）
```bash
pip3 install -r requirements.txt --break-system-packages
```

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

### 仮想環境が見つからない

次回のセッションで仮想環境を再度アクティベートする必要があります：
```bash
cd doge-trading-bot
source venv/bin/activate
```

## 開発

### テスト実行

```bash
# 1. まず接続テスト
python main.py test

# 2. 価格確認（テストネット）
python main.py price

# 3. 少額でテスト
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