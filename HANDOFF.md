# プロジェクト引き継ぎドキュメント

**プロジェクト名**: Multi-DEX Trading Bot (Paradex & Lighter)
**最終更新**: 2025-11-11
**前回セッションブランチ**: `claude/fix-websocket-execution-011CV1YZxjH7n6UCWgVdGG3J`
**最新コミット**: `eecfc54`

---

## 📋 プロジェクト概要

このボットは、**Paradex**と**Lighter**の2つの分散型取引所（DEX）で同時取引を実行する高度な自動取引システムです。

### 主要機能
- ✅ 同時取引実行（両取引所で同時に注文）
- ✅ WebSocketリアルタイム約定検知
- ✅ デルタニュートラル戦略（ヘッジポジション）
- ✅ ファンディングレートアービトラージ
- ✅ スプレッド監視機能
- ✅ 自動ポジションローテーション
- ✅ 緊急停止機能（Ctrl+C対応）

---

## 🏗️ アーキテクチャ

```
html/
├── bot/
│   ├── __init__.py               # パッケージ初期化
│   ├── config.py                 # 設定管理（環境変数/JSON）
│   ├── paradex_client.py         # Paradex API クライアント
│   ├── lighter_client.py         # Lighter API クライアント（WebSocket対応）
│   ├── trading_bot.py            # メイン取引ロジック
│   ├── auto_trader.py            # 自動取引ループ機能
│   ├── delta_neutral_strategy.py # デルタニュートラル戦略
│   └── notifier.py               # 通知機能
│
├── main.py                       # CLIエントリーポイント
│
├── .env.example                  # 環境変数テンプレート
├── config.example.json           # JSON設定テンプレート
│
├── requirements.txt              # Python依存関係
├── requirements_lighter.txt      # Lighter SDK専用依存関係
│
├── quickstart.sh                 # クイックセットアップスクリプト
├── setup.sh                      # セットアップスクリプト
├── install.sh                    # インストールスクリプト
│
├── README.md                     # プロジェクトドキュメント
├── WEBSOCKET_IMPLEMENTATION.md   # WebSocket実装詳細
├── FUNDING_RATE_ARBITRAGE.md     # ファンディングレート戦略詳細
├── MARKET_CONFIGURATION_GUIDE.md # マーケット設定ガイド
│
└── check_*.py / *.sh            # 各種ユーティリティスクリプト
```

---

## 🎯 コア機能詳細

### 1. ParadexClient (`bot/paradex_client.py`)

**責務**: Paradex取引所とのAPI通信

**主要メソッド**:
- `get_market_price()` - 現在の市場価格取得
- `place_market_order(side, size)` - 成行注文
- `place_limit_order(side, size, price)` - 指値注文
- `get_account_balance()` - 残高取得
- `get_funding_rate()` - ファンディングレート取得

**特徴**:
- SDK/REST APIフォールバック対応
- 自動エラーハンドリング
- タイムアウト設定（30秒）

---

### 2. LighterClient (`bot/lighter_client.py`)

**責務**: Lighter取引所とのAPI通信 + WebSocket約定監視

**主要メソッド**:
- `get_market_price()` - 現在の市場価格取得
- `place_market_order(side, size, reduce_only=False)` - 成行注文
- `place_limit_order(side, size, price, reduce_only=False)` - 指値注文
- `get_account_balance()` - 残高取得

**WebSocket機能** (NEW!):
- `subscribe_to_account_updates(callback)` - アカウント更新をリアルタイム監視
- `get_position_from_account(account_data)` - Account構造からポジション抽出
- `_parse_position(position_data)` - ポジションデータをパース

**特徴**:
- SDK/REST APIフォールバック対応
- WebSocketでの約定検知（環境変数で有効化）
- `reduce_only` パラメータ対応（ポジション決済専用注文）
- `expiry_time` 自動設定

---

### 3. TradingBot (`bot/trading_bot.py`)

**責務**: 取引ロジックの統合管理

**主要メソッド**:
- `test_connection()` - 接続テスト
- `get_prices()` - 両取引所の価格取得
- `execute_trade(side, amount)` - 同時取引実行
- `check_arbitrage(min_spread)` - アービトラージ機会検出
- `monitor_positions()` - ポジション監視

**特徴**:
- 非同期処理（asyncio）
- 両取引所での同時実行
- エラーハンドリングとロールバック

---

### 4. DeltaNeutralStrategy (`bot/delta_neutral_strategy.py`)

**責務**: デルタニュートラル戦略の実装

**主な戦略**:
```
Paradex LONG (買い) + Lighter SHORT (売り) = 価格変動リスク相殺
```

**主要メソッド**:
- `run_delta_neutral_loop()` - デルタニュートラルループ実行
- `open_delta_neutral_position()` - ポジションオープン
- `close_delta_neutral_position()` - ポジションクローズ
- `_wait_for_spread_convergence()` - スプレッド監視
- `_check_funding_rate_opportunity()` - ファンディングレート機会チェック

**スプレッド監視機能** (NEW!):
- 各取引所のbid-askスプレッドが設定値以下になるまで待機
- デフォルト: 0.02%以下で取引実行
- ポジションオープン時とクローズ時の両方で監視

**ファンディングレートアービトラージ** (NEW!):
- Paradexのファンディングレートのみ参照（シンプル化）
- 連続型ファンディング（保有時間に比例）
- 正ファンディング → Paradex SHORT + Lighter LONG
- 負ファンディング → Paradex LONG + Lighter SHORT

**WebSocket約定検知** (NEW!):
- `_wait_for_lighter_fill_via_websocket()` - WebSocketで約定監視
- `_place_lighter_limit_with_price_update()` - 指値注文 + WebSocket監視

**安全機能**:
- 片方失敗時の自動クリーンアップ（危険な片側ポジションを自動決済）
- Ctrl+C での安全停止（既存ポジションを自動決済）
- ポジション情報を `.current_position.json` に保存
- 起動時に既存ポジションを自動検知・復元

**P&L（損益）計算**:
- 各サイクル後に損益を計算・表示
- 累積損益を追跡

---

### 5. AutoTrader (`bot/auto_trader.py`)

**責務**: 自動取引ループ機能

**主要メソッド**:
- `run_loop()` - 自動取引ループ実行

**特徴**:
- ランダムなホールド時間（デフォルト2-3時間）
- ポジションを持つ → 待機 → 決済 → 反対方向で再オープン
- 最大繰り返し回数設定可能
- Ctrl+C で安全停止

---

## 🚀 最新の実装（前回セッション）

### ✅ 完了した機能

#### 1. WebSocket約定検知機能
- **ファイル**: `bot/lighter_client.py`, `bot/delta_neutral_strategy.py`
- **内容**: Lighterの指値注文後、WebSocketでリアルタイムに約定を検知
- **環境変数**: `LIGHTER_USE_WEBSOCKET=true`
- **メリット**: ポーリング不要、正確な約定タイミング検知

#### 2. スプレッド監視機能
- **ファイル**: `bot/delta_neutral_strategy.py`
- **内容**: 両取引所のbid-askスプレッドが0.02%以下になるまで待機
- **環境変数**: `SPREAD_MAX_PCT=0.02`, `SPREAD_CHECK_INTERVAL=2`
- **メリット**: より正確なヘッジ価格を確保、スリッページ最小化

#### 3. ファンディングレートアービトラージ（Paradex単独戦略）
- **ファイル**: `bot/delta_neutral_strategy.py`
- **内容**: Paradexのファンディングレートのみ参照して方向決定
- **環境変数**: `FUNDING_RATE_ENABLED=true`, `FUNDING_RATE_MIN_DIFF_PCT=0.3`
- **メリット**: シンプル、エラーが少ない、短時間保有に最適

#### 4. Ctrl+C ポジション決済機能
- **ファイル**: `bot/delta_neutral_strategy.py`
- **内容**: ボット停止時に既存ポジションを自動決済
- **実装**: `__init__` でポジション状態を復元、例外処理で決済実行
- **メリット**: 危険な片側ポジションを残さない

#### 5. OrderExpiry エラー修正
- **ファイル**: `bot/lighter_client.py`
- **内容**: `expiry_time` パラメータを自動設定（指値: 24時間、成行: 1時間）
- **実装**: `reduce_only` パラメータ対応

#### 6. ファンディングレートAPIの安定化
- **コミット履歴**:
  - `eecfc54` - ファンディングレートのしきい値チェックを削除
  - `37fecb3` - aiohttpセッションでtrust_env=Trueを有効化
  - `a292d08` - LighterクライアントのHTTPタイムアウトを10秒→30秒に延長
  - `f304bb9` - Lighter SDK create_orderからexpiry_timeパラメータを削除
  - `3ca6397` - ファンディングレート取得をfetch_markets_summary()に変更

---

## 🔧 設定ガイド

### 環境変数 (.env)

```bash
# Paradex設定
PARADEX_ENV=TESTNET
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

# デルタニュートラル戦略設定
DELTA_NEUTRAL_USD_AMOUNT=50      # 1ポジションあたりのUSD金額
DELTA_NEUTRAL_LEVERAGE=10        # レバレッジ倍率
DELTA_NEUTRAL_CAPITAL_PCT=0.5    # 証拠金の使用率（50%）
DELTA_NEUTRAL_MIN_HOURS=2.0      # 最小保持時間
DELTA_NEUTRAL_MAX_HOURS=3.0      # 最大保持時間

# スプレッド監視設定
SPREAD_MAX_PCT=0.02              # 最大許容bid-askスプレッド（%）
SPREAD_CHECK_INTERVAL=2          # チェック間隔（秒）
SPREAD_CHECK_TIMEOUT=0           # タイムアウト（秒）- 0=無限待機

# WebSocket設定
LIGHTER_USE_WEBSOCKET=true       # WebSocket約定検知を有効化

# ファンディングレートアービトラージ設定（Paradex単独）
FUNDING_RATE_ENABLED=true        # ファンディングレート機能を有効化
FUNDING_RATE_MIN_DIFF_PCT=0.3    # 最小絶対レート（%/8時間）
FUNDING_RATE_CHECK_INTERVAL=300  # チェック間隔（秒）
FUNDING_RATE_TARGET_APY=10.0     # 目標年率（%）
```

---

## 📝 使い方

### 基本コマンド

```bash
# 接続テスト（最初に実行推奨）
python main.py test

# 価格確認
python main.py price

# 同時取引
python main.py trade BUY 0.1
python main.py trade SELL 0.1

# アービトラージ検出
python main.py arbitrage --min-spread 0.5

# ポジション監視
python main.py monitor
```

### デルタニュートラル戦略

```bash
# 基本的な使い方
python main.py delta-neutral

# USD金額指定（50ドル分のポジション）
python main.py delta-neutral --usd-amount 50

# ホールド時間カスタマイズ（3-6分でテスト）
python main.py delta-neutral --usd-amount 50 --min-hours 0.05 --max-hours 0.1

# 最大サイクル数指定（5回で停止）
python main.py delta-neutral --usd-amount 100 --max-cycles 5

# 完全なカスタマイズ例
python main.py delta-neutral \
  --usd-amount 50 \
  --leverage 10 \
  --min-hours 2.0 \
  --max-hours 3.0 \
  --max-cycles 10
```

### 緊急停止（全ポジションクローズ）

```bash
# 自動検出（デルタニュートラル戦略のポジション情報を使用）
python main.py close-all

# サイズを手動指定
python main.py close-all --size 156

# Paradexのみ
python main.py close-all --paradex-only

# Lighterのみ
python main.py close-all --lighter-only
```

---

## ⚠️ 既知の問題と制限事項

### 1. SDK依存関係の競合
**問題**: `paradex_py`と`lighter-sdk`は`eth-account`パッケージのバージョン要件が競合
**解決策**: REST APIモードで使用（SDKなしでも完全動作）

### 2. WebSocketの安定性
**問題**: Lighter WebSocketが時々切断される可能性
**解決策**: 環境変数 `LIGHTER_USE_WEBSOCKET=false` でポーリングモードに切り替え

### 3. ファンディングレートAPI
**問題**: Lighter APIが時々タイムアウト
**解決策**: Paradex単独戦略を使用（より安定）

### 4. スプレッド監視
**制限**: タイムアウト設定が0（無限待機）の場合、流動性が低い時間帯に永久に待つ可能性
**推奨**: 本番環境では適切なタイムアウトを設定（例: 300秒）

---

## 🔜 次のステップ（TODOリスト）

### 優先度: 高

- [ ] **複数マーケットのサポート**
  - 現在: DOGEのみ
  - 目標: BTC, ETH, SOLなど複数マーケット対応
  - ファイル: `bot/config.py`, `main.py`

- [ ] **リスク管理機能の強化**
  - 最大ドローダウン制限
  - 累積損失時の自動停止
  - ポジションサイズの動的調整
  - ファイル: `bot/delta_neutral_strategy.py`

- [ ] **ログ・モニタリングの改善**
  - 構造化ログ（JSON形式）
  - リアルタイムダッシュボード
  - アラート機能（Slack/Discord/Telegram）
  - ファイル: `bot/notifier.py`, 新規 `bot/logger.py`

### 優先度: 中

- [ ] **バックテスト機能**
  - 過去データでの戦略検証
  - P&L シミュレーション
  - ファイル: 新規 `bot/backtester.py`

- [ ] **Web UI**
  - ポジション監視ダッシュボード
  - 戦略パラメータ調整
  - P&L グラフ表示
  - ディレクトリ: 新規 `web/`

- [ ] **データベース統合**
  - トレード履歴の永続化
  - P&L レポート生成
  - ファイル: 新規 `bot/database.py`

### 優先度: 低

- [ ] **マルチアカウント対応**
  - 複数のAPIキーで並行実行
  - ファイル: `bot/config.py`

- [ ] **高度な注文タイプ**
  - ストップロス
  - トレーリングストップ
  - OCO注文
  - ファイル: `bot/paradex_client.py`, `bot/lighter_client.py`

---

## 🧪 テスト手順

### 1. 初回セットアップ

```bash
# リポジトリをクローン
git clone https://github.com/0xnec0/html.git trading-bot
cd trading-bot

# ブランチを確認
git checkout claude/fix-websocket-execution-011CV1YZxjH7n6UCWgVdGG3J

# クイックスタート
./quickstart.sh

# 仮想環境をアクティベート
source venv/bin/activate

# 設定ファイル作成
cp .env.example .env
nano .env  # 認証情報を記入
```

### 2. 接続テスト

```bash
# 両取引所への接続確認
python main.py test

# 期待される出力:
# ✅ Paradex connection successful
# ✅ Lighter connection successful
```

### 3. 価格取得テスト

```bash
# 価格確認
python main.py price

# 期待される出力:
# Paradex: $0.8500
# Lighter: $0.8498
# Spread: 0.02%
```

### 4. デルタニュートラル戦略テスト（少額）

```bash
# テストネットで小額実行
python main.py delta-neutral --usd-amount 10 --max-cycles 1

# 期待される動作:
# 1. スプレッドチェック
# 2. ファンディングレートチェック
# 3. ポジションオープン（Paradex BUY + Lighter SELL）
# 4. 待機（2-3時間）
# 5. ポジションクローズ
# 6. P&L 表示
```

### 5. WebSocket機能テスト

```bash
# WebSocket有効で実行
LIGHTER_USE_WEBSOCKET=true python main.py delta-neutral --usd-amount 10

# ログで確認:
# 🔌 Subscribing to account updates for index XXX...
# 📊 Account Structure (first update): { ... }
# ✅ 約定確認！ポジション: -10.00
```

---

## 📚 ドキュメント

- **README.md** - プロジェクト全体の説明、使い方
- **WEBSOCKET_IMPLEMENTATION.md** - WebSocket実装の詳細
- **FUNDING_RATE_ARBITRAGE.md** - ファンディングレート戦略の詳細
- **MARKET_CONFIGURATION_GUIDE.md** - マーケット設定ガイド
- **HANDOFF.md** - このドキュメント（引き継ぎ用）

---

## 🔒 セキュリティ注意事項

⚠️ **重要**:
- 秘密鍵とAPIキーは絶対に共有しない
- `.env` ファイルは `.gitignore` に含める（既に含まれています）
- 本番環境では必ず MAINNET を使用
- テストネットで十分にテストしてから本番運用
- 初期は少額でテスト（USD 10-50程度）

---

## 💬 トラブルシューティング

### pip インストールエラー
```bash
error: externally-managed-environment
```
**解決策**: 仮想環境を使用
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### WebSocket接続エラー
```bash
❌ WebSocket subscription error: ...
```
**解決策**: ポーリングモードに切り替え
```bash
LIGHTER_USE_WEBSOCKET=false
```

### ファンディングレート取得エラー
```bash
❌ Failed to get funding rate from Paradex
```
**解決策**: ファンディングレート機能を無効化
```bash
FUNDING_RATE_ENABLED=false
```

---

## 📞 サポート

問題が発生した場合は、GitHubのIssuesセクションで報告してください。

---

## 🎉 まとめ

このプロジェクトは、高度な自動取引システムとして以下を実現しています：

✅ **安定性**: WebSocket + ポーリングのフォールバック
✅ **安全性**: 片方失敗時の自動クリーンアップ、Ctrl+C対応
✅ **効率性**: スプレッド監視、ファンディングレートアービトラージ
✅ **拡張性**: モジュール設計、設定ファイルで柔軟にカスタマイズ可能

---

**引き継ぎ準備完了！🚀**

新しいプロジェクトを始める際は、このドキュメントを参考にしてください。
