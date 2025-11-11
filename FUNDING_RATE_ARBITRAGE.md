# ファンディングレートアービトラージ機能（Paradex単独戦略）

## 📊 概要

このボットは、**Paradexのファンディングレートのみ**を参照して、デルタニュートラルポジションを構築します。

### 戦略の特徴

**シンプルさ重視**:
- ✅ Paradexのファンディングレートのみチェック
- ✅ Lighterは自動的に逆方向でヘッジ
- ✅ 短時間保有（2-3時間）に最適
- ✅ エラーが少なく安定動作

### Paradex連続型ファンディングの利点

| 項目 | Paradex (使用) | Lighter (未使用) |
|------|---------|---------|
| ファンディング方式 | **連続型** (保有時間比例) | 離散型 (1時間毎決済) |
| 短時間保有 | ✅ 2-3時間でも効果的 | ❌ 1時間未満は無効 |
| API安定性 | ✅ 大手で安定 | ⚠️ 時々失敗 |
| 実装複雑度 | ✅ シンプル | ❌ 差分計算が複雑 |

## 🎯 アービトラージ戦略

### 基本ロジック

1. **Paradexのファンディングレートを取得**
   - エンドポイント: `/v1/markets` (8時間レート)

2. **絶対値で閾値判断**
   - 閾値: デフォルト0.3%/8時間（年率約13.7%）
   - 絶対値が閾値以上なら機会あり

3. **ポジション方向決定**
   - **正ファンディング**: Paradex SHORT + Lighter LONG
   - **負ファンディング**: Paradex LONG + Lighter SHORT

### 収益機会の例

**シナリオ1: 強気相場（正ファンディング）**
```
Paradex:  +0.5%/8時間
戦略:     Paradex SHORT (ファンディング受取) + Lighter LONG (ヘッジ)
収益:     0.5% × 3回/日 × 365日 = 年率54.7%
実際:     短時間保有で年率約15-20%
```

**シナリオ2: 弱気相場（負ファンディング）**
```
Paradex:  -0.3%/8時間
戦略:     Paradex LONG (ファンディング受取) + Lighter SHORT (ヘッジ)
収益:     0.3% × 3回/日 × 365日 = 年率32.8%
実際:     短時間保有で年率約10-15%
```

## ⚙️ 設定

### 環境変数 (.env)

```bash
# ファンディングレートアービトラージを有効化（Paradex単独）
FUNDING_RATE_ENABLED=true

# 最小絶対レート（0.3% = Paradex 0.3%/8時間 ≈ 年率13.7%）
FUNDING_RATE_MIN_DIFF_PCT=0.3

# ファンディングレートチェック間隔（秒）
FUNDING_RATE_CHECK_INTERVAL=300

# 目標年率（参考値）
FUNDING_RATE_TARGET_APY=10.0
```

### Config.py プロパティ

```python
@property
def funding_rate_enabled(self) -> bool:
    """ファンディングレートアービトラージを有効化（Paradex単独）"""

@property
def funding_rate_min_diff_pct(self) -> float:
    """ポジションをオープンする最小絶対レート（%/8時間）"""

@property
def funding_rate_check_interval(self) -> float:
    """ファンディングレートチェック間隔（秒）"""

@property
def funding_rate_target_apy(self) -> float:
    """目標年率（%）"""
```

## 🔧 実装詳細

### APIメソッド

#### Paradex Client（使用）
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

#### ファンディングレート機会チェック（Paradex単独）
```python
async def _check_funding_rate_opportunity() -> Optional[Dict[str, Any]]:
    """
    ファンディングレートアービトラージ機会をチェック（Paradex単独戦略）

    Returns:
        {
            'opportunity': bool,           # ポジションを持つべきか
            'paradex_rate': float,         # Paradex 8時間レート
            'paradex_rate_8h': float,      # 同上
            'estimated_apy': float,        # 推定年率
            'recommendation': str,         # 'PARADEX_SHORT_LIGHTER_LONG', etc.
            'paradex_side': str,           # 'BUY' or 'SELL'
            'lighter_side': str,           # 'BUY' or 'SELL' (ヘッジ)
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
💹 Paradexファンディングレートをチェック中...
   Paradex: +0.4000%/8時間 (連続型)
   推定APY: 43.80%
   ✅ 機会あり: PARADEX_SHORT_LIGHTER_LONG
   理由: Paradex positive funding (+0.4000%) → SHORT receives payment
   Paradex: SELL, Lighter: BUY (ヘッジ)
```

## 📊 ポジション情報

ポジションオープン時、以下の情報が `.current_position.json` に保存されます：

```json
{
  "timestamp": "2025-01-15T10:00:00",
  "size": 10.0,
  "paradex_price": 0.8523,
  "lighter_price": 0.8519,
  "paradex_side": "SELL",
  "lighter_side": "BUY",
  "funding_check": {
    "opportunity": true,
    "paradex_rate": 0.004,
    "paradex_rate_8h": 0.004,
    "estimated_apy": 43.8,
    "recommendation": "PARADEX_SHORT_LIGHTER_LONG",
    "paradex_side": "SELL",
    "lighter_side": "BUY",
    "reason": "Paradex positive funding (+0.4000%) → SHORT receives payment"
  }
}
```

## 🎓 参考資料

- [Lighter ファンディング機構](https://docs.lighter.xyz/perpetual-futures/funding)
- [Paradex ファンディング機構](https://docs.paradex.trade/risk/funding-mechanism)

## 📝 注意事項

- ファンディングレートは市場状況により変動します
- 推定APYは理論値で、実際の収益は保有時間に依存します
- **短時間保有（2-3時間）**では理論APYの一部のみ実現
- Paradexの連続型ファンディングは保有時間に比例配分されます
- リスク管理を適切に行い、資金を分散してください

## 💡 Paradex単独戦略を選んだ理由

1. **シンプルさ**: API呼び出し1回、エラーが少ない
2. **短時間保有**: Paradex連続型は2-3時間でも効果的
3. **安定性**: Paradex API は大手で信頼性が高い
4. **保守性**: コードが簡潔で理解しやすい
