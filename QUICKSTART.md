# 🚀 クイックスタートガイド

このガイドでは、5分でボットを起動して最初の取引を実行する方法を説明します。

## 📋 必要なもの

- Python 3.8以上
- Paradexアカウント（TESTNETまたはMAINNET）
- Lighterアカウント
- 取引用の資金

## ステップ1: インストール

```bash
# リポジトリをクローン
git clone https://github.com/your-repo/trading-bot.git
cd trading-bot

# 自動セットアップ（仮想環境も自動作成）
./quickstart.sh

# 仮想環境をアクティベート
source venv/bin/activate
```

## ステップ2: 設定ファイルを作成

```bash
# .env.exampleをコピー
cp .env.example .env

# エディタで開く
nano .env
```

## ステップ3: 必要な情報を記入

### Paradex設定

```bash
PARADEX_ENV=TESTNET  # または MAINNET
PARADEX_L1_ADDRESS=0x...  # あなたのEthereum L1アドレス
PARADEX_L1_PRIVATE_KEY=0x...  # L1秘密鍵
PARADEX_MARKET=JUP-USD-PERP  # 取引したいマーケット
```

### Lighter設定

```bash
LIGHTER_PRIVATE_KEY=0x...  # API key秘密鍵
LIGHTER_ACCOUNT_INDEX=0  # アカウントインデックス
LIGHTER_API_KEY_INDEX=2  # APIキーインデックス（2-254）
LIGHTER_MARKET=JUP  # 取引したいマーケット
LIGHTER_USE_WEBSOCKET=true  # WebSocket約定検知を有効化
```

#### Lighterアカウント情報の取得方法

1. あなたのL1アドレスでアカウント情報を取得：
```bash
curl "https://mainnet.zklighter.elliot.ai/api/v1/accountsByL1Address?l1_address=0xYOUR_ADDRESS"
```

2. `account_index`をメモ

### 取引設定（オプション）

```bash
# 基本設定
TRADE_AMOUNT=0.1
SLIPPAGE_TOLERANCE=0.5
EXECUTION_TIMEOUT=30

# デルタニュートラル戦略
DELTA_NEUTRAL_USD_AMOUNT=50  # 1ポジションあたり$50
DELTA_NEUTRAL_LEVERAGE=10  # 10倍レバレッジ
DELTA_NEUTRAL_MIN_HOURS=2.0  # 最小2時間保持
DELTA_NEUTRAL_MAX_HOURS=3.0  # 最大3時間保持

# ファンディングレート裁定
FUNDING_RATE_ENABLED=true  # 有効化
FUNDING_RATE_MIN_DIFF_PCT=0.3  # 最小0.3%/8h
```

## ステップ4: 接続テスト

```bash
python main.py test
```

✅ 両取引所への接続が成功したことを確認

## ステップ5: 価格を確認

```bash
python main.py price
```

現在の価格とスプレッドを確認

## ステップ6: 戦略を選択

### オプションA: ファンディングレート裁定（推奨）

Paradexのファンディングレートを利用して利益を狙う戦略：

```bash
# デフォルト設定で実行
python main.py delta-neutral

# カスタム設定で実行
python main.py delta-neutral --usd-amount 50 --min-hours 2 --max-hours 3
```

**仕組み：**
1. Paradexのファンディングレートをチェック
2. プラスなら: Paradex SHORT + Lighter LONG
3. マイナスなら: Paradex LONG + Lighter SHORT
4. 2-3時間保持してクローズ
5. 繰り返し

### オプションB: 手動取引

```bash
# 価格差を確認
python main.py arbitrage

# 手動で取引
python main.py trade BUY 0.1
```

### オプションC: 緊急停止

ポジションをすぐにクローズしたい場合：

```bash
python main.py close-all
```

## 💡 重要なポイント

### ✅ 安全機能

- **Lighter指値 → Paradex成行**のロジック
  - Lighterで約定確認してからParadexで実行
  - 片側だけポジションを持つリスクを回避

- **WebSocket約定検知**
  - リアルタイムで約定を検知
  - 高速で正確な実行

- **自動リトライ**
  - 失敗時は10秒後に自動リトライ

### ⚠️ リスク管理

1. **小額から始める**
   - 最初は$10-50程度でテスト

2. **レバレッジに注意**
   - デフォルトは10倍
   - リスク許容度に応じて調整

3. **ファンディングレートの確認**
   - プラスとマイナスが頻繁に入れ替わる
   - 長期間同じ方向は危険

4. **流動性の確認**
   - スプレッドが広い時は取引を避ける

### 🛑 停止方法

**安全な停止:**
```
Ctrl + C を1回押す
```

→ 現在のサイクルを完了してから停止

**緊急停止:**
```
Ctrl + C を2回押す
```

→ すぐに停止（ポジションは手動でクローズが必要）

## 🔍 トラブルシューティング

### エラー: "expiry_time"

```
❌ got an unexpected keyword argument 'expiry_time'
```

→ 既に修正済み。最新版にアップデート

### エラー: "Cannot connect to host"

```
❌ Cannot connect to host mainnet.zklighter.elliot.ai:443
```

→ ネットワーク接続を確認。プロキシ設定が必要な場合があります

### エラー: "Lighter注文が約定していません"

```
❌ Lighter注文が約定していません
```

→ 正常な動作。価格が合わずに約定しなかった場合、自動的にリトライします

### エラー: "Unclosed client session"

```
ERROR:asyncio:Unclosed client session
```

→ 既に修正済み。最新版にアップデート

## 📊 ログの見方

```
✅ = 成功
❌ = エラー
⚠️ = 警告
💰 = 価格情報
📊 = ポジション情報
🔄 = 実行中
⏰ = 時間情報
```

## 🎯 次のステップ

1. ✅ テストネットで数日間テスト
2. ✅ 利益/損失を記録
3. ✅ 設定を最適化
4. ✅ 本番環境に移行（慎重に）

## 📚 さらに詳しく

- [README.md](README.md) - 完全なドキュメント
- [FUNDING_RATE_ARBITRAGE.md](FUNDING_RATE_ARBITRAGE.md) - ファンディングレート裁定の詳細
- [MARKET_CONFIGURATION_GUIDE.md](MARKET_CONFIGURATION_GUIDE.md) - マーケット設定ガイド

---

**質問や問題がある場合は、GitHubのIssuesで報告してください！**
