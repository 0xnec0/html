#!/bin/bash
# API接続テストスクリプト
# ParadexとLighterのAPIエンドポイントが正しく動作しているか確認

set -e  # エラーが発生したら終了

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 DOGE Trading Bot - API接続テスト"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# カラー設定
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 1. Paradex Testnet API テスト
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${BLUE}📊 1. Paradex (Testnet) API テスト${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "エンドポイント: https://api.testnet.paradex.trade/v1/markets"
echo ""

PARADEX_RESPONSE=$(curl -s -w "\n%{http_code}" "https://api.testnet.paradex.trade/v1/markets" 2>&1)
PARADEX_HTTP_CODE=$(echo "$PARADEX_RESPONSE" | tail -n1)
PARADEX_BODY=$(echo "$PARADEX_RESPONSE" | sed '$d')

if [ "$PARADEX_HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ 接続成功 (HTTP $PARADEX_HTTP_CODE)${NC}"
    echo ""

    # DOGEマーケットを検索
    echo "🔎 DOGEマーケットを検索中..."
    DOGE_FOUND=$(echo "$PARADEX_BODY" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    results = data.get('results', [])
    for market in results:
        if 'DOGE' in market.get('symbol', ''):
            print(json.dumps(market, indent=2))
            break
    else:
        print('Not found')
except:
    print('Error parsing JSON')
" 2>&1)

    if [ "$DOGE_FOUND" != "Not found" ] && [ "$DOGE_FOUND" != "Error parsing JSON" ]; then
        echo -e "${GREEN}✓ DOGE-USD-PERP マーケットが見つかりました！${NC}"
        echo "$DOGE_FOUND" | head -20
    else
        echo -e "${YELLOW}⚠ DOGEマーケットが見つかりませんでした${NC}"
    fi
else
    echo -e "${RED}✗ 接続失敗 (HTTP $PARADEX_HTTP_CODE)${NC}"
    echo "レスポンス: $PARADEX_BODY" | head -5
fi

echo ""
echo ""

# 2. Paradex Mainnet API テスト
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${BLUE}📊 2. Paradex (Mainnet) API テスト${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "エンドポイント: https://api.prod.paradex.trade/v1/markets"
echo ""

PARADEX_PROD_RESPONSE=$(curl -s -w "\n%{http_code}" "https://api.prod.paradex.trade/v1/markets" 2>&1)
PARADEX_PROD_HTTP_CODE=$(echo "$PARADEX_PROD_RESPONSE" | tail -n1)
PARADEX_PROD_BODY=$(echo "$PARADEX_PROD_RESPONSE" | sed '$d')

if [ "$PARADEX_PROD_HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ 接続成功 (HTTP $PARADEX_PROD_HTTP_CODE)${NC}"
    echo ""

    # DOGEマーケットを検索
    echo "🔎 DOGEマーケットを検索中..."
    DOGE_FOUND=$(echo "$PARADEX_PROD_BODY" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    results = data.get('results', [])
    for market in results:
        if 'DOGE' in market.get('symbol', ''):
            print(json.dumps(market, indent=2))
            break
    else:
        print('Not found')
except:
    print('Error parsing JSON')
" 2>&1)

    if [ "$DOGE_FOUND" != "Not found" ] && [ "$DOGE_FOUND" != "Error parsing JSON" ]; then
        echo -e "${GREEN}✓ DOGE-USD-PERP マーケットが見つかりました！${NC}"
        echo "$DOGE_FOUND" | head -20
    else
        echo -e "${YELLOW}⚠ DOGEマーケットが見つかりませんでした${NC}"
    fi
else
    echo -e "${RED}✗ 接続失敗 (HTTP $PARADEX_PROD_HTTP_CODE)${NC}"
    echo "レスポンス: $PARADEX_PROD_BODY" | head -5
fi

echo ""
echo ""

# 3. Lighter API テスト
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${BLUE}📊 3. Lighter (Mainnet) API テスト${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "エンドポイント: https://mainnet.zklighter.elliot.ai/markets"
echo ""

LIGHTER_RESPONSE=$(curl -s -w "\n%{http_code}" "https://mainnet.zklighter.elliot.ai/markets" 2>&1)
LIGHTER_HTTP_CODE=$(echo "$LIGHTER_RESPONSE" | tail -n1)
LIGHTER_BODY=$(echo "$LIGHTER_RESPONSE" | sed '$d')

if [ "$LIGHTER_HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ 接続成功 (HTTP $LIGHTER_HTTP_CODE)${NC}"
    echo ""

    # DOGEマーケットを検索
    echo "🔎 DOGEマーケットを検索中..."
    DOGE_FOUND=$(echo "$LIGHTER_BODY" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if isinstance(data, list):
        markets = data
    else:
        markets = data.get('markets', data.get('results', []))

    for market in markets:
        market_name = market.get('symbol', market.get('market', market.get('name', '')))
        if 'DOGE' in market_name.upper():
            print(json.dumps(market, indent=2))
            break
    else:
        print('Not found')
except Exception as e:
    print(f'Error: {e}')
" 2>&1)

    if [ "$DOGE_FOUND" != "Not found" ] && [[ ! "$DOGE_FOUND" =~ ^Error ]]; then
        echo -e "${GREEN}✓ DOGE マーケットが見つかりました！${NC}"
        echo "$DOGE_FOUND" | head -20
    else
        echo -e "${YELLOW}⚠ DOGEマーケットが見つかりませんでした${NC}"
    fi
else
    echo -e "${RED}✗ 接続失敗 (HTTP $LIGHTER_HTTP_CODE)${NC}"
    echo "レスポンス: $LIGHTER_BODY" | head -5
fi

echo ""
echo ""

# 4. サマリー
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${BLUE}📋 テスト結果サマリー${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ "$PARADEX_HTTP_CODE" = "200" ]; then
    echo -e "Paradex Testnet: ${GREEN}✓ OK${NC}"
else
    echo -e "Paradex Testnet: ${RED}✗ NG (HTTP $PARADEX_HTTP_CODE)${NC}"
fi

if [ "$PARADEX_PROD_HTTP_CODE" = "200" ]; then
    echo -e "Paradex Mainnet: ${GREEN}✓ OK${NC}"
else
    echo -e "Paradex Mainnet: ${RED}✗ NG (HTTP $PARADEX_PROD_HTTP_CODE)${NC}"
fi

if [ "$LIGHTER_HTTP_CODE" = "200" ]; then
    echo -e "Lighter Mainnet: ${GREEN}✓ OK${NC}"
else
    echo -e "Lighter Mainnet: ${RED}✗ NG (HTTP $LIGHTER_HTTP_CODE)${NC}"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✅ テスト完了${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
