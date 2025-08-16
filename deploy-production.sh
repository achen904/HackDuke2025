#!/bin/bash

# Production Deployment Script for Duke Eats
# Run this on your production server at dukebdeats.colab.duke.edu

echo "🚀 Duke Eats Production Deployment"
echo "=================================="

# Check if we're in the right directory
if [ ! -f "server.py" ]; then
    echo "❌ Error: server.py not found. Please run this script from the project root."
    exit 1
fi

echo "📥 Pulling latest changes from GitHub..."
git pull origin main

if [ $? -eq 0 ]; then
    echo "✅ Successfully pulled latest changes"
else
    echo "❌ Failed to pull changes. Please check your git status."
    exit 1
fi

echo "🔧 Updating production configuration..."
# Update the production config to use the production URL
sed -i 's|API_BASE_URL: .*|API_BASE_URL: "https://dukebdeats.colab.duke.edu",|' production-config.js

echo "📦 Installing/updating dependencies..."
# Update Python dependencies
pip install -r requirements.txt

# Update Node.js dependencies
npm install

echo "🏗️ Building frontend for production..."
npm run build

if [ $? -eq 0 ]; then
    echo "✅ Frontend built successfully"
else
    echo "❌ Frontend build failed"
    exit 1
fi

echo "🔄 Restarting production server..."
# Kill existing server processes
pkill -f "python3 server.py" || true
pkill -f "python server.py" || true

# Wait a moment for processes to stop
sleep 2

# Start the production server
echo "🚀 Starting production server..."
export FLASK_ENV=production
export NODE_ENV=production
python3 server.py &

echo "⏳ Waiting for server to start..."
sleep 5

# Check if server is running
if curl -s http://localhost:3000/api/health > /dev/null; then
    echo "✅ Production server is running successfully!"
    echo "🌐 Your Duke Eats application is now live at: https://dukebdeats.colab.duke.edu"
else
    echo "❌ Server failed to start. Please check the logs."
    exit 1
fi

echo ""
echo "🎉 Deployment completed successfully!"
echo "📱 Your beautiful Duke Eats UI is now live with all the latest features!"
