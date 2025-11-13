#!/bin/bash
# Quick Download and Setup Script
# Usage: curl -sSL https://raw.githubusercontent.com/0xnec0/html/claude/xmr-trading-ui-research-011CUtURFcnaRZf8jgeD7ML7/download.sh | bash

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}XMR Trading Bot - Quick Download${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

BRANCH="claude/xmr-trading-ui-research-011CUtURFcnaRZf8jgeD7ML7"
TARGET_DIR="${TARGET_DIR:-xmr-trading-bot}"

if [ -d "$TARGET_DIR" ]; then
    echo "Directory $TARGET_DIR already exists."
    read -p "Remove and re-download? [y/N]: " remove_existing
    if [[ $remove_existing =~ ^[Yy]$ ]]; then
        rm -rf "$TARGET_DIR"
    else
        echo "Exiting..."
        exit 0
    fi
fi

echo "Downloading from GitHub..."
git clone -b "$BRANCH" https://github.com/0xnec0/html.git "$TARGET_DIR"

cd "$TARGET_DIR"

echo ""
echo -e "${GREEN}Download complete!${NC}"
echo ""
echo "Next steps:"
echo "  cd $TARGET_DIR"
echo "  ./setup.sh"
echo ""
