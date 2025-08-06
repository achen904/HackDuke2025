#!/bin/bash

# Direct VM Setup for Duke Eats (OpenAI only)
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

print_status "Setting up VM for Duke Eats deployment (OpenAI only)..."

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
cd $APP_DIR

# Create docker-compose.yml for production
print_status "Creating docker-compose.yml..."
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  duke-eats:
    image: ghcr.io/achen904/hackduke2025:latest
    container_name: duke-eats-app
    ports:
      - "3000:3000"
    environment:
      - FLASK_ENV=production
      - PYTHONUNBUFFERED=1
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - OPENAI_API_BASE=${OPENAI_API_BASE:-https://litellm.oit.duke.edu}
    volumes:
      - ./duke_nutrition.db:/app/duke_nutrition.db
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    networks:
      - duke-eats-network

  nginx:
    image: nginx:alpine
    container_name: duke-eats-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - duke-eats
    restart: unless-stopped
    networks:
      - duke-eats-network
    profiles:
      - production

networks:
  duke-eats-network:
    driver: bridge
EOF

# Create .env file template (will be overwritten by CI/CD)
print_status "Creating environment file template..."
cat > .env << 'EOF'
# This file will be automatically updated by GitHub Actions
# with the API key from GitHub secrets
OPENAI_API_KEY=will_be_set_by_github_actions
OPENAI_API_BASE=https://litellm.oit.duke.edu
DATABASE_URL=sqlite:///duke_nutrition.db
EOF

# Create basic nginx.conf
print_status "Creating nginx configuration..."
cat > nginx.conf << 'EOF'
events {
    worker_connections 1024;
}

http {
    upstream duke_eats_backend {
        server duke-eats:3000;
    }

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=general:10m rate=30r/s;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types
        text/plain
        text/css
        text/xml
        text/javascript
        application/json
        application/javascript
        application/xml+rss
        application/atom+xml
        image/svg+xml;

    server {
        listen 80;
        server_name localhost;

        # Security headers
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header Referrer-Policy "no-referrer-when-downgrade" always;
        add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;

        # API routes with rate limiting
        location /api/ {
            limit_req zone=api burst=20 nodelay;
            proxy_pass http://duke_eats_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_connect_timeout 30s;
            proxy_send_timeout 30s;
            proxy_read_timeout 30s;
        }

        # Static files
        location / {
            limit_req zone=general burst=50 nodelay;
            proxy_pass http://duke_eats_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            
            # Cache static assets
            location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
                expires 1y;
                add_header Cache-Control "public, immutable";
                proxy_pass http://duke_eats_backend;
            }
        }

        # Health check endpoint
        location /health {
            access_log off;
            return 200 "healthy\n";
            add_header Content-Type text/plain;
        }
    }
}
EOF

# Create database file placeholder
print_status "Creating database placeholder..."
touch duke_nutrition.db

# Set up SSL directory
print_status "Creating SSL directory..."
mkdir -p ssl
chmod 700 ssl

# Create update script
print_status "Creating update script..."
cat > update-app.sh << 'EOF'
#!/bin/bash
echo "🔄 Updating Duke Eats application..."
docker-compose pull
docker-compose up -d
docker image prune -f
echo "✅ Update complete!"
EOF
chmod +x update-app.sh

# Create systemd service
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

print_success "VM setup completed successfully!"
print_warning "⚠️  Important next steps:"
echo ""
echo "1.  Login to GitHub Container Registry:"
echo "   docker login ghcr.io -u YOUR_GITHUB_USERNAME"
echo ""
echo "2. � Add GitHub Secrets (including OPENAI_API_KEY):"
echo "   Go to: GitHub Repository → Settings → Secrets and variables → Actions"
echo ""
echo "3. 🚀 Deploy by pushing to main branch or triggering GitHub Actions"
echo ""
echo "4. 🌐 Access your application at:"
echo "   http://$(curl -s ifconfig.me):3000"
echo ""
print_status "Application directory: $APP_DIR"
print_status "API key will be automatically set by GitHub Actions"
