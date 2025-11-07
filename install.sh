#!/bin/bash
# XMR Trading Bot - Quick Install Script
# One-liner: curl -sSL https://raw.githubusercontent.com/your-repo/install.sh | bash

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}XMR Trading Bot - Quick Install${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

# Check if git is installed
if ! command -v git &> /dev/null; then
    echo "Git is not installed. Please install git first."
    exit 1
fi

# Clone repository
REPO_URL="${REPO_URL:-https://github.com/0xnec0/html.git}"
TARGET_DIR="${TARGET_DIR:-xmr-trading-bot}"

echo "Cloning repository..."
if [ -d "$TARGET_DIR" ]; then
    echo "Directory $TARGET_DIR already exists."
    read -p "Remove and re-clone? [y/N]: " remove_existing
    if [[ $remove_existing =~ ^[Yy]$ ]]; then
        rm -rf "$TARGET_DIR"
        git clone "$REPO_URL" "$TARGET_DIR"
    else
        cd "$TARGET_DIR"
        git pull
    fi
else
    git clone "$REPO_URL" "$TARGET_DIR"
fi

cd "$TARGET_DIR"

# Run setup script
if [ -f "setup.sh" ]; then
    echo ""
    echo "Running setup script..."
    bash setup.sh
else
    echo "Setup script not found. Please run manually."
    exit 1
fi

echo ""
echo -e "${GREEN}Installation complete!${NC}"
echo "Run 'cd $TARGET_DIR' to get started."
