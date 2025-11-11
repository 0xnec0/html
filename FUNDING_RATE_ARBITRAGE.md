# ファンディングレートアービトラージ機能

## 📊 概要

このボットは、LighterとParadexのファンディングレート差を利用したアービトラージ戦略を実装しています。

### 両プラットフォームの違い

| 項目 | Lighter | Paradex |
|------|---------|---------|
| ファンディング方式 | **離散型** (1時間毎決済) | **連続型** (保有時間比例) |
| 支払いタイミング | 毎時0分 | 8時間毎（3回/日） |
| レート上限 | ±0.5%/時 | ±5%/年 |
| 決済方法 | 時間経過で満額受取 | 保有時間に比例配分 |

## 🎯 アービトラージ戦略

### 基本ロジック

1. **両取引所のファンディングレートを取得**
   - Lighter: `/api/v1/fundings` (時間レート)
   - Paradex: `/v1/markets` (8時間レート)

2. **レート差を計算**
   - Paradexの8時間レートを時間レートに変換 (÷8)
   - 両取引所の時間レートの差を算出
   - 年率換算（APY）を推定

3. **ポジション判断**
   - レート差が閾値以上 → ポジションオープン
   - レート差が閾値未満 → スキップ

### 収益機会の例

**シナリオ1: 強気相場（ポジティブファンディング）**
```
Lighter:  +0.01%/時 (離散型で満額受取)
Paradex:  +0.005%/時 (連続型で比例配分)
差額:     +0.005%/時
戦略:     Lighter SHORT + Paradex LONG
年率:     約10-15% APY
```

**シナリオ2: 弱気相場（ネガティブファンディング）**
```
Lighter:  -0.01%/時
Paradex:  -0.005%/時
差額:     +0.005%/時
戦略:     標準戦略を維持 (Paradex LONG + Lighter SHORT)
年率:     約8-12% APY
```

## ⚙️ 設定

### 環境変数 (.env)

```bash
# ファンディングレートアービトラージを有効化
FUNDING_RATE_ENABLED=true

# 最小レート差（0.5% = 時間0.5%の差が必要）
FUNDING_RATE_MIN_DIFF_PCT=0.5

# ファンディングレートチェック間隔（秒）
FUNDING_RATE_CHECK_INTERVAL=300

# 目標年率（参考値）
FUNDING_RATE_TARGET_APY=10.0
```

### Config.py プロパティ

```python
@property
def funding_rate_enabled(self) -> bool:
    """ファンディングレートアービトラージを有効化"""

@property
def funding_rate_min_diff_pct(self) -> float:
    """ポジションをオープンする最小レート差（%）"""

@property
def funding_rate_check_interval(self) -> float:
    """ファンディングレートチェック間隔（秒）"""

@property
def funding_rate_target_apy(self) -> float:
    """目標年率（%）"""
```

## 🔧 実装詳細

### APIメソッド

#### Lighter Client
```python
async def get_funding_rate() -> Optional[Dict[str, Any]]:
    """
    Lighterのファンディングレートを取得

    Returns:
        {
            'funding_rate': float,       # 時間レート (0.0001 = 0.01%)
            'funding_rate_pct': float,   # パーセント表示
            'next_funding_time': int,    # 次回決済時刻
            'market': str,               # マーケット名
            'source': str                # 'SDK' or 'REST'
        }
    """
```

#### Paradex Client
```python
async def get_funding_rate() -> Optional[Dict[str, Any]]:
    """
    Paradexのファンディングレートを取得

    Returns:
        {
            'funding_rate': float,          # 8時間レート
            'funding_rate_pct': float,      # パーセント表示
            'funding_rate_annual': float,   # 年率換算
            'next_funding_time': int,       # 次回決済時刻
            'market': str,                  # マーケット名
            'source': str                   # 'SDK' or 'REST:endpoint'
        }
    """
```

### 戦略メソッド

#### ファンディングレート機会チェック
```python
async def _check_funding_rate_opportunity() -> Optional[Dict[str, Any]]:
    """
    ファンディングレートアービトラージ機会をチェック

    Returns:
        {
            'opportunity': bool,           # ポジションを持つべきか
            'lighter_rate': float,         # Lighter時間レート
            'paradex_rate': float,         # Paradex時間レート
            'rate_diff_pct': float,        # レート差（%）
            'estimated_apy': float,        # 推定年率
            'recommendation': str,         # 'LIGHTER_SHORT', 'NO_POSITION', etc.
            'reason': str                  # 判断理由
        }
    """
```

### ポジションオープンフロー

```
1. 価格取得
   ↓
2. ファンディングレートチェック
   ├─ レート差 < 閾値 → スキップ
   └─ レート差 >= 閾値 → 続行
   ↓
3. ポジションサイズ計算
   ↓
4. 注文実行
   ↓
5. ポジション情報保存（ファンディングレート情報含む）
```

## 📈 期待収益

### 小規模運用（1-5 BTC相当）
- **年率**: 8-12%
- **リスク**: 低
- **流動性**: 十分

### 中規模運用（10-50 BTC相当）
- **年率**: 10-15%
- **リスク**: 中
- **流動性**: 十分

### 大規模運用（100+ BTC相当）
- **年率**: 5-8%
- **リスク**: 中〜高
- **流動性**: 制約あり

## ⚠️ リスク管理

### 主要リスク

1. **ファンディングレート急変動**
   - 上限: Lighter ±0.5%/時、Paradex ±5%/年
   - 対策: リアルタイム監視とポジション調整

2. **取引所間接続障害**
   - 対策: エラーハンドリングと自動リトライ

3. **流動性リスク**
   - 対策: ポジションサイズ制限

4. **ベーシスリスク**
   - パーペチュアル価格とスポット価格の乖離
   - 対策: 価格差監視

## 🚀 使用方法

### 1. 設定を有効化

```bash
# .env ファイルを編集
FUNDING_RATE_ENABLED=true
FUNDING_RATE_MIN_DIFF_PCT=0.5
```

### 2. ボットを実行

```bash
# デルタニュートラル戦略を実行
python main.py delta-neutral --leverage 10
```

### 3. ログを確認

```
💹 ファンディングレートアービトラージ機会をチェック中...
   Lighter: 0.0100%/時 (離散型)
   Paradex: 0.0050%/時 (連続型、0.0400%/8時間)
   差額: 0.0050%/時
   推定APY: 12.50%
   ✅ 機会あり: LIGHTER_SHORT
   理由: Lighter rate (0.0100%) > Paradex rate (0.0050%)
```

## 📊 ポジション情報

ポジションオープン時、以下の情報が `.current_position.json` に保存されます：

```json
{
  "timestamp": "2025-01-15T10:00:00",
  "size": 10.0,
  "paradex_price": 0.8523,
  "lighter_price": 0.8519,
  "funding_check": {
    "opportunity": true,
    "lighter_rate": 0.0001,
    "paradex_rate": 0.00005,
    "rate_diff_pct": 0.005,
    "estimated_apy": 12.5,
    "recommendation": "LIGHTER_SHORT",
    "reason": "Lighter rate (0.0100%) > Paradex rate (0.0050%)"
  }
}
```

## 🎓 参考資料

- [Lighter ファンディング機構](https://docs.lighter.xyz/perpetual-futures/funding)
- [Paradex ファンディング機構](https://docs.paradex.trade/risk/funding-mechanism)

## 📝 注意事項

- ファンディングレートは市場状況により変動します
- 推定APYは過去データに基づく概算値です
- 実際の収益は保有時間、市場ボラティリティ、手数料などに依存します
- リスク管理を適切に行い、資金を分散してください
