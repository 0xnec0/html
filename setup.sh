#!/bin/bash
# XMR Trading Bot - Setup Script
# This script helps you set up the trading bot quickly

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print functions
print_header() {
    echo -e "${BLUE}============================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}============================================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Main setup
print_header "XMR Trading Bot - Setup"

# Check Python
print_info "Checking Python installation..."
if command_exists python3; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    print_success "Python found: $PYTHON_VERSION"
    PYTHON_CMD="python3"
elif command_exists python; then
    PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
    print_success "Python found: $PYTHON_VERSION"
    PYTHON_CMD="python"
else
    print_error "Python not found! Please install Python 3.8 or higher."
    exit 1
fi

# Check pip
print_info "Checking pip installation..."
if command_exists pip3; then
    print_success "pip3 found"
    PIP_CMD="pip3"
elif command_exists pip; then
    print_success "pip found"
    PIP_CMD="pip"
else
    print_error "pip not found! Please install pip."
    exit 1
fi

# Check if virtual environment should be used
echo ""
read -p "Do you want to create a virtual environment? (recommended) [Y/n]: " use_venv
use_venv=${use_venv:-Y}

if [[ $use_venv =~ ^[Yy]$ ]]; then
    print_info "Creating virtual environment..."

    if [ -d "venv" ]; then
        print_warning "Virtual environment already exists. Skipping creation."
    else
        $PYTHON_CMD -m venv venv
        print_success "Virtual environment created"
    fi

    print_info "Activating virtual environment..."
    source venv/bin/activate
    print_success "Virtual environment activated"

    PYTHON_CMD="python"
    PIP_CMD="pip"
fi

# Install dependencies
echo ""
print_info "Installing dependencies..."
$PIP_CMD install -r requirements.txt

if [ $? -eq 0 ]; then
    print_success "Dependencies installed successfully"
else
    print_error "Failed to install dependencies"
    exit 1
fi

# Create configuration file
echo ""
print_info "Setting up configuration..."

if [ -f ".env" ]; then
    print_warning ".env file already exists"
    read -p "Do you want to overwrite it? [y/N]: " overwrite_env
    overwrite_env=${overwrite_env:-N}

    if [[ $overwrite_env =~ ^[Yy]$ ]]; then
        cp .env.example .env
        print_success "Configuration file created from template"
    else
        print_info "Keeping existing .env file"
    fi
else
    cp .env.example .env
    print_success "Configuration file created from template"
fi

# Interactive configuration
echo ""
read -p "Do you want to configure the bot now? [y/N]: " configure_now
configure_now=${configure_now:-N}

if [[ $configure_now =~ ^[Yy]$ ]]; then
    print_header "Configuration Setup"

    echo ""
    echo "Please enter your credentials:"
    echo ""

    # Paradex configuration
    print_info "Paradex Configuration"
    read -p "Environment (TESTNET/MAINNET) [TESTNET]: " paradex_env
    paradex_env=${paradex_env:-TESTNET}

    read -p "Paradex L1 Address (0x...): " paradex_l1_addr
    read -sp "Paradex L1 Private Key (0x...): " paradex_l1_key
    echo ""

    read -p "Paradex Market [XMR-USD-PERP]: " paradex_market
    paradex_market=${paradex_market:-XMR-USD-PERP}

    echo ""

    # Lighter configuration
    print_info "Lighter Configuration"
    read -p "Lighter API Key: " lighter_api_key
    read -sp "Lighter API Secret: " lighter_api_secret
    echo ""
    read -sp "Lighter Private Key (0x...): " lighter_private_key
    echo ""

    read -p "Lighter Market [XMR]: " lighter_market
    lighter_market=${lighter_market:-XMR}

    echo ""

    # Trading configuration
    print_info "Trading Configuration"
    read -p "Trade Amount [0.1]: " trade_amount
    trade_amount=${trade_amount:-0.1}

    read -p "Slippage Tolerance [0.5]: " slippage
    slippage=${slippage:-0.5}

    # Write configuration
    cat > .env <<EOF
# Paradex Configuration
PARADEX_ENV=${paradex_env}
PARADEX_L1_ADDRESS=${paradex_l1_addr}
PARADEX_L1_PRIVATE_KEY=${paradex_l1_key}
PARADEX_MARKET=${paradex_market}

# Lighter Configuration
LIGHTER_API_KEY=${lighter_api_key}
LIGHTER_API_SECRET=${lighter_api_secret}
LIGHTER_PRIVATE_KEY=${lighter_private_key}
LIGHTER_MARKET=${lighter_market}

# Trading Configuration
TRADE_AMOUNT=${trade_amount}
SLIPPAGE_TOLERANCE=${slippage}
EXECUTION_TIMEOUT=30
EOF

    print_success "Configuration saved to .env"
else
    print_warning "Please edit .env file manually before running the bot"
fi

# Test installation
echo ""
print_info "Testing installation..."
$PYTHON_CMD main.py --help >/dev/null 2>&1

if [ $? -eq 0 ]; then
    print_success "Installation test passed"
else
    print_error "Installation test failed"
    exit 1
fi

# Create convenience scripts
print_info "Creating convenience scripts..."

# Run script
cat > run.sh <<'EOF'
#!/bin/bash
# Quick run script

if [ -d "venv" ]; then
    source venv/bin/activate
fi

python main.py "$@"
EOF
chmod +x run.sh
print_success "Created run.sh"

# Summary
echo ""
print_header "Setup Complete!"
echo ""
print_success "The XMR Trading Bot has been set up successfully!"
echo ""
print_info "Next steps:"
echo ""
echo "  1. Edit .env file with your credentials (if not done already):"
echo "     nano .env"
echo ""
echo "  2. Test the connection:"
if [[ $use_venv =~ ^[Yy]$ ]]; then
    echo "     source venv/bin/activate"
fi
echo "     python main.py price"
echo ""
echo "  3. Start trading:"
echo "     python main.py trade BUY 0.1"
echo ""
print_info "Quick commands:"
echo "  - Check prices:        python main.py price"
echo "  - Execute trade:       python main.py trade BUY 0.1"
echo "  - Check arbitrage:     python main.py arbitrage"
echo "  - Monitor positions:   python main.py monitor"
echo ""
if [ -f "run.sh" ]; then
    echo "  Or use the convenience script:"
    echo "    ./run.sh price"
    echo ""
fi
print_warning "IMPORTANT: Always test on TESTNET before using MAINNET!"
echo ""
print_header "Happy Trading! 🚀"
