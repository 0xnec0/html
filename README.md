# MetaMask dApp with Synpress Testing

SynpressとNode.jsを使用したMetaMask接続テスト用のdAppプロジェクトです。

## 概要

このプロジェクトは以下を含みます：
- シンプルなMetaMask接続対応のdApp
- Synpressを使用した自動E2Eテスト
- MetaMaskの接続、署名、トランザクション送信のテスト

## プロジェクト構成

```
.
├── index.html                      # dApp HTMLファイル
├── package.json                    # プロジェクト設定と依存関係
├── synpress.config.js              # Synpress設定ファイル
├── tests/
│   └── e2e/
│       ├── specs/
│       │   └── metamask-connection.spec.js  # テストケース
│       └── support/
│           ├── e2e.js              # Cypressサポートファイル
│           └── commands.js         # カスタムコマンド
└── README.md                       # このファイル
```

## 必要な環境

- Node.js (v16以上推奨)
- npm または yarn
- Ubuntu/Linux環境
- Chrome/Chromiumブラウザ

## セットアップ手順

### 1. 依存関係のインストール

```bash
npm install
```

### 2. dAppの起動

別のターミナルウィンドウでdAppサーバーを起動：

```bash
npm run serve
```

これで `http://localhost:3000` でdAppが利用可能になります。

### 3. テストの実行

#### ヘッドレスモードでテスト実行：

```bash
npm run test:headless
```

#### GUIモードでテスト実行：

```bash
npm run test:open
```

または：

```bash
npm test
```

## テストの内容

`tests/e2e/specs/metamask-connection.spec.js` には以下のテストケースが含まれています：

1. **MetaMask接続テスト** - dAppとMetaMaskの接続を確認
2. **残高取得テスト** - 接続後にETH残高を取得
3. **メッセージ署名テスト** - personal_signを使用した署名
4. **トランザクション送信テスト** - テストトランザクションの送信
5. **UI状態テスト** - ボタンの有効/無効状態の確認

## dAppの機能

### 主な機能：
- MetaMaskへの接続
- アカウントアドレスの表示
- チェーンIDの表示
- ETH残高の取得
- メッセージの署名
- テストトランザクションの送信

### 使用方法：

1. ブラウザで `http://localhost:3000` にアクセス
2. 「MetaMaskに接続」ボタンをクリック
3. MetaMaskで接続を承認
4. 各種機能ボタンを使用してテスト

## 注意事項

### テスト用秘密鍵について

テストコード内の秘密鍵は**Hardhatのデフォルトテストアカウント**です：
- アドレス: `0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266`
- 秘密鍵: `0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80`

**警告**: この秘密鍵は公開されているため、本番環境では絶対に使用しないでください！

### ネットワーク設定

デフォルトではSepoliaテストネットを使用します。必要に応じて：
- `tests/e2e/specs/metamask-connection.spec.js` 内のネットワーク設定を変更
- テスト用ETHを取得（Sepolia Faucetなど）

## トラブルシューティング

### テストが失敗する場合：

1. **dAppサーバーが起動しているか確認**
   ```bash
   npm run serve
   ```

2. **依存関係を再インストール**
   ```bash
   rm -rf node_modules package-lock.json
   npm install
   ```

3. **Cypressキャッシュをクリア**
   ```bash
   npx cypress cache clear
   npx cypress install
   ```

### MetaMask拡張機能のエラー：

Synpressは自動的にMetaMask拡張機能をインストールします。手動での設定は不要です。

## 開発

### カスタムテストの追加

`tests/e2e/specs/` ディレクトリに新しい `.spec.js` ファイルを作成してください。

### カスタムコマンドの追加

`tests/e2e/support/commands.js` にCypressカスタムコマンドを追加できます。

## 参考リンク

- [Synpress公式ドキュメント](https://github.com/Synthetixio/synpress)
- [Cypress公式ドキュメント](https://www.cypress.io/)
- [MetaMask開発者ドキュメント](https://docs.metamask.io/)

## ライセンス

MIT
