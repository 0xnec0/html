# 依存関係競合解決テスト

## 🎯 目的
paradex-pyとlighter-sdkのeth-account依存競合を解決

## 📋 試す順序

### Option D: 最新バージョンテスト（推奨・最速）

```bash
# 1. 新しいvenv作成（クリーンな環境）
cd ~/projects/grvt-edgex-bot
python3 -m venv venv-test
source venv-test/bin/activate

# 2. 最新版インストール（pre-release含む）
pip install --pre paradex-py lighter-sdk python-dotenv aiohttp websockets

# 3. 依存関係確認
pip list | grep -E "paradex|lighter|eth-account"

# 4. 動作テスト
python test_paradex.py
python test_lighter.py
```

**期待結果：**
- eth-accountが0.13.4以上でインストールされる
- paradex-pyが0.13.4に対応していればOK！

---

### Option E: Poetry使用（Option Dがダメなら）

```bash
# 1. Poetryインストール
pip install poetry

# 2. プロジェクト初期化
cd ~/projects/grvt-edgex-bot
poetry init --no-interaction

# 3. パッケージ追加
poetry add paradex-py lighter-sdk python-dotenv aiohttp websockets

# 4. 環境に入る
poetry shell

# 5. テスト実行
python test_paradex.py
```

---

### Option F: 強制インストール（自己責任）

```bash
# 依存チェックをスキップして強制インストール
pip install paradex-py lighter-sdk --no-deps
pip install python-dotenv aiohttp websockets eth-account==0.13.4

# ⚠️ 注意: 動作不良の可能性あり！テスト必須！
python test_paradex.py
```

---

## ✅ 成功確認チェックリスト

- [ ] `pip install` がエラーなく完了
- [ ] `python test_paradex.py` が成功
- [ ] `python test_lighter.py` が成功
- [ ] `python test_lighter_websocket.py` が成功

すべてOKなら → `test_lighter_order_cancel.py`（発注→キャンセル）実装へ！

---

## 🔍 トラブルシューティング

### エラー: `ERROR: Cannot install...`
→ Option EまたはFを試す

### エラー: `ImportError: cannot import name...`
→ eth-accountのAPIが変わった可能性。Option Fで特定バージョンを指定

### 成功したら
元のvenvにも反映:
```bash
deactivate
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-test-latest.txt
```
