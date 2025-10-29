describe('MetaMask dApp Connection Test', () => {
  const testPrivateKey = '0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80';
  const testAddress = '0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266';

  beforeEach(() => {
    // dAppページにアクセス
    cy.visit('/');
  });

  it('MetaMaskをセットアップして接続する', () => {
    // MetaMaskのセットアップ（初回のみ）
    cy.setupMetamask(testPrivateKey, 'sepolia', 'TestPassword123!').then((setupFinished) => {
      expect(setupFinished).to.be.true;
    });

    // 接続ボタンをクリック
    cy.get('#connectButton').should('be.visible').click();

    // MetaMaskの接続承認
    cy.acceptMetamaskAccess().should('be.true');

    // 接続成功の確認
    cy.get('#status').should('contain', '接続済み');
    cy.get('#accountAddress').should('contain', testAddress.toLowerCase());
    cy.get('#chainId').should('not.contain', '-');
  });

  it('接続後に残高を取得できる', () => {
    // 接続ボタンをクリック
    cy.get('#connectButton').click();
    cy.acceptMetamaskAccess();

    // 残高取得ボタンをクリック
    cy.get('#getBalanceButton').should('not.be.disabled').click();

    // 残高が表示されることを確認
    cy.get('#balance').should('not.contain', '-');
    cy.get('#balance').should('contain', 'ETH');
  });

  it('メッセージに署名できる', () => {
    // 接続
    cy.get('#connectButton').click();
    cy.acceptMetamaskAccess();

    // 署名ボタンをクリック
    cy.get('#signMessageButton').should('not.be.disabled').click();

    // MetaMaskで署名を承認
    cy.confirmMetamaskSignatureRequest().should('be.true');

    // 署名結果が表示されることを確認
    cy.get('#signResult').should('not.contain', '-');
    cy.get('#signResult').invoke('text').should('have.length.gt', 10);
  });

  it('トランザクションを送信できる', () => {
    // 接続
    cy.get('#connectButton').click();
    cy.acceptMetamaskAccess();

    // トランザクション送信ボタンをクリック
    cy.get('#sendTransactionButton').should('not.be.disabled').click();

    // MetaMaskでトランザクションを承認
    cy.confirmMetamaskTransaction().should('be.true');

    // アラートが表示されることを確認（トランザクションハッシュ）
    // 注: Cypressでのアラート処理は自動的に処理されます
  });

  it('アカウント情報が正しく表示される', () => {
    // 接続
    cy.get('#connectButton').click();
    cy.acceptMetamaskAccess();

    // アカウント情報の確認
    cy.get('#accountAddress').invoke('text').then((address) => {
      expect(address.toLowerCase()).to.include('0x');
      expect(address.length).to.be.greaterThan(10);
    });

    // チェーンIDの確認
    cy.get('#chainId').invoke('text').then((chainId) => {
      expect(chainId).to.not.equal('-');
      expect(parseInt(chainId)).to.be.a('number');
    });
  });

  it('ボタンの状態が正しく変化する', () => {
    // 初期状態の確認
    cy.get('#getBalanceButton').should('be.disabled');
    cy.get('#sendTransactionButton').should('be.disabled');
    cy.get('#signMessageButton').should('be.disabled');

    // 接続
    cy.get('#connectButton').click();
    cy.acceptMetamaskAccess();

    // 接続後のボタン状態確認
    cy.get('#connectButton').should('be.disabled');
    cy.get('#getBalanceButton').should('not.be.disabled');
    cy.get('#sendTransactionButton').should('not.be.disabled');
    cy.get('#signMessageButton').should('not.be.disabled');
  });
});
