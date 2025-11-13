#!/bin/bash
# XMR Trading Bot - Deployment Script
# Deploy the bot to a server or production environment

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

print_header "XMR Trading Bot - Deployment"

# Check if .env exists
if [ ! -f ".env" ]; then
    print_error ".env file not found!"
    print_info "Please create .env file with your credentials before deploying."
    exit 1
fi

# Deployment options
echo ""
echo "Select deployment method:"
echo "1) Local (systemd service)"
echo "2) Docker"
echo "3) Docker Compose"
echo "4) Manual"
echo ""
read -p "Choose [1-4]: " deployment_method

case $deployment_method in
    1)
        print_header "Deploying as systemd service"

        SERVICE_NAME="xmr-trading-bot"
        SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
        WORKING_DIR=$(pwd)

        print_info "Creating systemd service..."

        sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=XMR Trading Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$WORKING_DIR
Environment="PATH=$WORKING_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$WORKING_DIR/venv/bin/python $WORKING_DIR/main.py monitor
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

        print_success "Service file created"

        print_info "Enabling and starting service..."
        sudo systemctl daemon-reload
        sudo systemctl enable "$SERVICE_NAME"
        sudo systemctl start "$SERVICE_NAME"

        print_success "Service started"
        print_info "Service status:"
        sudo systemctl status "$SERVICE_NAME" --no-pager

        echo ""
        print_info "Useful commands:"
        echo "  - Check status: sudo systemctl status $SERVICE_NAME"
        echo "  - View logs: sudo journalctl -u $SERVICE_NAME -f"
        echo "  - Stop: sudo systemctl stop $SERVICE_NAME"
        echo "  - Restart: sudo systemctl restart $SERVICE_NAME"
        ;;

    2)
        print_header "Deploying with Docker"

        print_info "Creating Dockerfile..."
        cat > Dockerfile <<'EOF'
FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Make main.py executable
RUN chmod +x main.py

# Default command
CMD ["python", "main.py", "--help"]
EOF

        print_success "Dockerfile created"

        print_info "Building Docker image..."
        docker build -t xmr-trading-bot:latest .

        print_success "Docker image built"

        print_info "Running container..."
        docker run -d \
            --name xmr-trading-bot \
            --env-file .env \
            --restart unless-stopped \
            xmr-trading-bot:latest \
            python main.py monitor

        print_success "Container started"

        echo ""
        print_info "Useful commands:"
        echo "  - View logs: docker logs -f xmr-trading-bot"
        echo "  - Stop: docker stop xmr-trading-bot"
        echo "  - Start: docker start xmr-trading-bot"
        echo "  - Execute command: docker exec xmr-trading-bot python main.py price"
        ;;

    3)
        print_header "Deploying with Docker Compose"

        print_info "Creating docker-compose.yml..."
        cat > docker-compose.yml <<'EOF'
version: '3.8'

services:
  trading-bot:
    build: .
    container_name: xmr-trading-bot
    env_file:
      - .env
    restart: unless-stopped
    command: python main.py monitor
    volumes:
      - ./logs:/app/logs
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
EOF

        print_success "docker-compose.yml created"

        # Create Dockerfile if not exists
        if [ ! -f "Dockerfile" ]; then
            print_info "Creating Dockerfile..."
            cat > Dockerfile <<'EOF'
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x main.py

CMD ["python", "main.py", "--help"]
EOF
        fi

        print_info "Starting services with docker-compose..."
        docker-compose up -d --build

        print_success "Services started"

        echo ""
        print_info "Useful commands:"
        echo "  - View logs: docker-compose logs -f"
        echo "  - Stop: docker-compose down"
        echo "  - Restart: docker-compose restart"
        echo "  - Execute command: docker-compose exec trading-bot python main.py price"
        ;;

    4)
        print_header "Manual Deployment"

        print_info "Manual deployment checklist:"
        echo ""
        echo "1. Ensure Python 3.8+ is installed"
        echo "2. Create virtual environment: python3 -m venv venv"
        echo "3. Activate: source venv/bin/activate"
        echo "4. Install dependencies: pip install -r requirements.txt"
        echo "5. Configure .env file"
        echo "6. Test: python main.py price"
        echo "7. Set up process manager (pm2, supervisor, etc.)"
        echo ""
        print_info "For production, consider using:"
        echo "  - systemd (option 1)"
        echo "  - Docker (option 2 or 3)"
        echo "  - PM2: pm2 start main.py --interpreter python3 --name xmr-bot"
        ;;

    *)
        print_error "Invalid option"
        exit 1
        ;;
esac

echo ""
print_header "Deployment Complete! 🚀"
print_warning "Remember to test thoroughly before using with real funds!"
