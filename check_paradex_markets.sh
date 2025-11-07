#!/bin/bash
# Paradexで利用可能なマーケットを確認するスクリプト

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 Paradex - 利用可能なマーケット一覧"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "📊 Paradex Mainnet - 全マーケット取得中..."
curl -s "https://api.prod.paradex.trade/v1/markets" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    results = data.get('results', [])
    print(f'\n✓ {len(results)} マーケットが見つかりました\n')

    # DOGEを検索
    print('🔎 DOGEを検索中...')
    doge_found = False
    for market in results:
        if 'DOGE' in market.get('market', '').upper():
            print(f'  ✓ 見つかりました: {market.get(\"market\")}')
            doge_found = True

    if not doge_found:
        print('  ✗ DOGEマーケットは見つかりませんでした')

    # 人気のアルトコインを表示
    print('\n📋 利用可能な主要アルトコイン:')
    altcoins = []
    for market in results:
        market_name = market.get('market', '')
        # USD-PERPで終わるもの
        if '-USD-PERP' in market_name:
            coin = market_name.replace('-USD-PERP', '')
            if coin not in ['BTC', 'ETH'] and len(coin) <= 5:
                altcoins.append(market_name)

    for coin in sorted(altcoins)[:20]:
        print(f'  • {coin}')

    if len(altcoins) > 20:
        print(f'  ... and {len(altcoins) - 20} more')

except Exception as e:
    print(f'Error: {e}')
"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
