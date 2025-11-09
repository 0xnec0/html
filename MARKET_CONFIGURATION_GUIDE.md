# Lighter マーケット設定ガイド

## 問題: "Market not found" エラー

ボットで以下のようなエラーが表示される場合：

```
[DEBUG-Lighter] Market ENA not found in order_book_details
[DEBUG-Lighter] Empty orderbook: asks=0, bids=0
❌ 価格取得失敗、リトライ中...
```

これは、設定されたマーケットが利用できないか、オーダーブックが空の状態を示しています。

## 解決方法

### 1. 利用可能なマーケットを確認

以下のコマンドで、Lighterで現在取引可能なマーケットを確認できます：

```bash
python3 check_lighter_markets.py
```

このスクリプトは以下を表示します：
- 全マーケット一覧
- 各マーケットの流動性（アクティブかどうか）
- ENAマーケットの状態（存在する場合）
- 推奨マーケット（流動性があるもの）

### 2. 設定を更新

#### 方法A: 環境変数で設定（推奨）

`.env` ファイルを作成または編集：

```bash
# .env ファイル
LIGHTER_MARKET=JUP  # 利用可能なマーケットシンボルに変更
```

#### 方法B: 環境変数を直接エクスポート

```bash
export LIGHTER_MARKET=JUP
```

#### 方法C: config.json で設定

`config.json` ファイルを作成または編集：

```json
{
  "lighter": {
    "market": "JUP"
  }
}
```

そして起動時に指定：

```bash
python main.py delta-neutral --loop --config config.json
```

### 3. Paradexのマーケットも合わせて変更

Delta Neutral戦略では、ParadexとLighterで **同じアセット** を取引する必要があります。

例：
- Lighter: `JUP` → Paradex: `JUP-USD-PERP`
- Lighter: `DOGE` → Paradex: `DOGE-USD-PERP`

`.env` ファイルで両方を設定：

```bash
# Paradex設定
PARADEX_MARKET=JUP-USD-PERP

# Lighter設定
LIGHTER_MARKET=JUP
```

## 一般的なマーケット

Lighterで一般的に利用可能なマーケット：

- `JUP` - Jupiter
- `DOGE` - Dogecoin
- `SOL` - Solana
- `BTC` - Bitcoin
- `ETH` - Ethereum

⚠️ **注意**: マーケットの利用可能性は変動します。取引前に必ず `check_lighter_markets.py` で確認してください。

## トラブルシューティング

### 問題: マーケットは存在するが、オーダーブックが空

```
⚠️ Empty orderbook: asks=0, bids=0
```

**原因**: マーケットに流動性がない

**解決策**:
1. 別のマーケットを選択
2. 流動性が戻るまで待つ
3. `check_lighter_markets.py` で流動性のあるマーケットを確認

### 問題: プロキシエラー

```
❌ Timeout: APIへの接続がタイムアウトしました
```

**解決策**:
1. プロキシ設定を確認（`.env` の `USE_PROXY`, `PROXY_SERVER` など）
2. プロキシ認証情報が正しいか確認
3. ネットワーク接続を確認

### 問題: 価格が取得できない

```
[74] ❌ 価格取得失敗、リトライ中...
```

**原因**:
- マーケットが見つからない
- ネットワーク接続の問題
- API制限

**解決策**:
1. `check_lighter_markets.py` でマーケットを確認
2. マーケット設定を修正
3. プロキシ設定を確認
4. 数分待ってから再試行

## 推奨設定例

### JUPでデルタニュートラル取引

```bash
# .env
PARADEX_MARKET=JUP-USD-PERP
LIGHTER_MARKET=JUP
DELTA_NEUTRAL_USD_AMOUNT=50
DELTA_NEUTRAL_LEVERAGE=10
SPREAD_MAX_PCT=0.02
```

実行：
```bash
python main.py delta-neutral --loop
```

### DOGEでデルタニュートラル取引

```bash
# .env
PARADEX_MARKET=DOGE-USD-PERP
LIGHTER_MARKET=DOGE
DELTA_NEUTRAL_USD_AMOUNT=50
DELTA_NEUTRAL_LEVERAGE=10
SPREAD_MAX_PCT=0.02
```

実行：
```bash
python main.py delta-neutral --loop
```

## 参考

- Lighter API: https://mainnet.zklighter.elliot.ai
- Lighter Docs: (公式ドキュメントのURL)
- Paradex Docs: https://docs.paradex.trade

---

💡 **ヒント**: 本番環境で使用する前に、必ずテスト環境で設定を確認してください！

```bash
python main.py test  # 接続テスト
python main.py price  # 価格取得テスト
```
