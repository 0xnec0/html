// カスタムCypressコマンドをここに定義できます

// 例: cy.waitForMetaMask() のようなカスタムコマンド
Cypress.Commands.add('waitForMetaMask', () => {
  cy.wait(1000);
});
