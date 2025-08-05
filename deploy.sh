#!/bin/bash

# Duke Eats Deployment Script
# This script automates the deployment of the Duke Eats application using Docker

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
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

# Check if Docker is installed
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    print_success "Docker and Docker Compose are installed"
}

# Check if .env file exists
check_env_file() {
    if [ ! -f .env ]; then
        print_warning ".env file not found. Creating template..."
        cat > .env << EOF
# Duke Eats Environment Variables
# Add your API keys here

GEMINI_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here

# Optional: Database configuration
# DATABASE_URL=sqlite:///duke_nutrition.db
EOF
        print_warning "Please edit .env file and add your API keys before running the deployment again."
        exit 1
    fi
    
    # Check if API keys are set
    if grep -q "your_gemini_api_key_here" .env || grep -q "your_openai_api_key_here" .env; then
        print_warning "Please update the .env file with your actual API keys before deployment."
        exit 1
    fi
    
    print_success "Environment file is properly configured"
}

# Build and deploy the application
deploy_app() {
    local profile=${1:-default}
    
    print_status "Starting deployment with profile: $profile"
    
    # Stop existing containers
    print_status "Stopping existing containers..."
    docker-compose down --remove-orphans
    
    # Build the application
    print_status "Building Docker image..."
    docker-compose build --no-cache
    
    # Start the application
    print_status "Starting the application..."
    if [ "$profile" = "production" ]; then
        docker-compose --profile production up -d
    else
        docker-compose up -d
    fi
    
    # Wait for the application to be ready
    print_status "Waiting for application to be ready..."
    sleep 10
    
    # Check if the application is running
    if curl -f http://localhost:3000/api/health > /dev/null 2>&1; then
        print_success "Application is running successfully!"
        print_status "Access your application at: http://localhost:3000"
        if [ "$profile" = "production" ]; then
            print_status "Production access at: http://localhost:80"
        fi
    else
        print_error "Application failed to start. Check logs with: docker-compose logs"
        exit 1
    fi
}

# Show logs
show_logs() {
    print_status "Showing application logs..."
    docker-compose logs -f
}

# Stop the application
stop_app() {
    print_status "Stopping the application..."
    docker-compose down
    print_success "Application stopped"
}

# Clean up everything
cleanup() {
    print_status "Cleaning up Docker resources..."
    docker-compose down --volumes --remove-orphans
    docker system prune -f
    print_success "Cleanup completed"
}

# Show status
show_status() {
    print_status "Application status:"
    docker-compose ps
}

# Main script logic
main() {
    case "${1:-deploy}" in
        "deploy")
            check_docker
            check_env_file
            deploy_app
            ;;
        "deploy:prod")
            check_docker
            check_env_file
            deploy_app "production"
            ;;
        "logs")
            show_logs
            ;;
        "stop")
            stop_app
            ;;
        "status")
            show_status
            ;;
        "cleanup")
            cleanup
            ;;
        "help"|"-h"|"--help")
            echo "Duke Eats Deployment Script"
            echo ""
            echo "Usage: $0 [command]"
            echo ""
            echo "Commands:"
            echo "  deploy        Deploy the application (default)"
            echo "  deploy:prod   Deploy with production profile (nginx)"
            echo "  logs          Show application logs"
            echo "  stop          Stop the application"
            echo "  status        Show application status"
            echo "  cleanup       Clean up all Docker resources"
            echo "  help          Show this help message"
            ;;
        *)
            print_error "Unknown command: $1"
            echo "Use '$0 help' for usage information"
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@" 