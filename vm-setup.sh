#!/bin/bash

# VM Setup Script for Duke Eats Application
# Run this script on your VM to prepare it for deployment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   print_error "This script should not be run as root"
   exit 1
fi

print_status "Setting up VM for Duke Eats deployment..."

# Update system
print_status "Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install Docker
print_status "Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    print_success "Docker installed successfully"
else
    print_success "Docker is already installed"
fi

# Install Docker Compose
print_status "Installing Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    print_success "Docker Compose installed successfully"
else
    print_success "Docker Compose is already installed"
fi

# Create application directory
APP_DIR="/opt/duke-eats"
print_status "Creating application directory at $APP_DIR..."
sudo mkdir -p $APP_DIR
sudo chown $USER:$USER $APP_DIR

# Navigate to app directory
cd $APP_DIR

# Download necessary files from repository
print_status "Downloading configuration files..."
curl -o docker-compose.yml https://raw.githubusercontent.com/achen904/HackDuke2025/main/docker-compose.prod.yml
curl -o nginx.conf https://raw.githubusercontent.com/achen904/HackDuke2025/main/nginx.conf

# Create .env file template
print_status "Creating environment file template..."
cat > .env << 'EOF'
# Duke Eats Environment Variables
# Replace with your actual API keys

GEMINI_API_KEY=your_actual_gemini_api_key_here
OPENAI_API_KEY=your_actual_openai_api_key_here

# Optional: Database configuration
DATABASE_URL=sqlite:///duke_nutrition.db
EOF

# Download database file (if exists)
print_status "Downloading database file..."
if curl -f -o duke_nutrition.db https://raw.githubusercontent.com/achen904/HackDuke2025/main/duke_nutrition.db; then
    print_success "Database downloaded successfully"
else
    print_warning "Database file not found in repository - will be created on first run"
    touch duke_nutrition.db
fi

# Set up SSL directory (for future HTTPS setup)
print_status "Creating SSL directory..."
mkdir -p ssl
chmod 700 ssl

# Create a simple update script
print_status "Creating update script..."
cat > update-app.sh << 'EOF'
#!/bin/bash
# Quick update script for Duke Eats

echo "🔄 Updating Duke Eats application..."

# Pull latest image
docker-compose pull

# Restart services
docker-compose up -d

# Clean up old images
docker image prune -f

echo "✅ Update complete!"
EOF

chmod +x update-app.sh

# Create systemd service for auto-start
print_status "Creating systemd service..."
sudo tee /etc/systemd/system/duke-eats.service > /dev/null << EOF
[Unit]
Description=Duke Eats Application
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$APP_DIR
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable duke-eats.service

# Setup log rotation
print_status "Setting up log rotation..."
sudo tee /etc/logrotate.d/duke-eats > /dev/null << 'EOF'
/var/lib/docker/containers/*/*-json.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 root root
    postrotate
        /bin/kill -USR1 $(cat /var/run/docker.pid 2>/dev/null) 2>/dev/null || true
    endscript
}
EOF

print_success "VM setup completed successfully!"
print_warning "⚠️  Important next steps:"
echo ""
echo "1. 📝 Edit the .env file with your actual API keys:"
echo "   nano $APP_DIR/.env"
echo ""
echo "2. 🔑 Add GitHub Container Registry access (if repository is private):"
echo "   docker login ghcr.io -u YOUR_GITHUB_USERNAME"
echo ""
echo "3. 🚀 Test the deployment:"
echo "   cd $APP_DIR && docker-compose up -d"
echo ""
echo "4. 🌐 Access your application at:"
echo "   http://$(curl -s ifconfig.me):3000"
echo ""
echo "5. 📊 Monitor with:"
echo "   docker-compose logs -f"
echo ""
print_status "Application directory: $APP_DIR"
print_status "Service management: sudo systemctl {start|stop|status} duke-eats"
print_status "Update command: $APP_DIR/update-app.sh"
