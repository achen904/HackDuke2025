#!/bin/bash

# Duke Eats Deployment Script

echo "Duke Eats Deployment Script"
echo "============================"

if [ "$1" = "production" ]; then
    echo "Switching to PRODUCTION configuration..."
    
    # Update production config
    sed -i '' 's|API_BASE_URL: .*|API_BASE_URL: "https://dukebdeats.colab.duke.edu",|' production-config.js
    
    echo "✅ Production configuration updated"
    echo "🔗 Backend URL: https://dukebdeats.colab.duke.edu"
    echo "🌐 Frontend URL: https://dukebdeats.colab.duke.edu"
    
elif [ "$1" = "local" ]; then
    echo "Switching to LOCAL configuration..."
    
    # Update local config
    sed -i '' 's|API_BASE_URL: .*|API_BASE_URL: "http://localhost:3000",|' production-config.js
    
    echo "✅ Local configuration updated"
    echo "🔗 Backend URL: http://localhost:3000"
    echo "🌐 Frontend URL: http://localhost:5173"
    
else
    echo "Usage: $0 [production|local]"
    echo ""
    echo "Commands:"
    echo "  production  - Switch to production configuration"
    echo "  local       - Switch to local development configuration"
    echo ""
    echo "Current configuration:"
    echo "Production: https://dukebdeats.colab.duke.edu"
    echo "Local: http://localhost:3000"
    echo ""
    echo "To switch configurations, use:"
    echo "  ./deploy.sh production  - for production"
    echo "  ./deploy.sh local       - for local development"
fi
