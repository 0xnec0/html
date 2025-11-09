#!/bin/bash
# DOGE Trading Bot - Quick Start Script
# Automatically sets up virtual environment and installs dependencies

set -e  # Exit on error

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}🚀 DOGE Trading Bot - Quick Start${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${YELLOW}⚠ Python3 not found. Please install Python 3.8+${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Python3 found: $(python3 --version)${NC}"
echo ""

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo -e "${BLUE}📦 Creating virtual environment...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${YELLOW}⚠ Virtual environment already exists${NC}"
fi

echo ""
echo -e "${BLUE}🔧 Activating virtual environment...${NC}"

# Activate virtual environment
source venv/bin/activate

echo -e "${GREEN}✓ Virtual environment activated${NC}"
echo ""

# Install dependencies
echo -e "${BLUE}📥 Installing dependencies...${NC}"
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo -e "${GREEN}✅ Setup complete!${NC}"
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}📝 Next Steps:${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "1. Copy configuration file:"
echo "   cp .env.example .env"
echo ""
echo "2. Edit .env with your credentials:"
echo "   nano .env"
echo ""
echo "3. Test API connections:"
echo "   ./test_api.sh"
echo ""
echo "4. Activate virtual environment (in future sessions):"
echo "   source venv/bin/activate"
echo ""
echo "5. Test bot connection:"
echo "   python main.py test"
echo ""
echo "6. Check DOGE prices:"
echo "   python main.py price"
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${YELLOW}💡 Tip: Run 'source venv/bin/activate' to activate the virtual environment${NC}"
echo ""
