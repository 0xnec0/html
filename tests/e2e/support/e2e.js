import '@synthetixio/synpress/support/index';

// カスタムコマンドやグローバル設定をここに追加できます

Cypress.on('uncaught:exception', (err, runnable) => {
  // アプリケーションからの予期しないエラーを無視
  // テストの失敗を防ぐため
  return false;
});
