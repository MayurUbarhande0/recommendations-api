#!/bin/bash

# Scalable Recommendation API - Setup Script
# This script sets up the entire system for production use

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}============================================${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Main setup
main() {
    print_header "Recommendation API Setup"
    
    # Check prerequisites
    print_info "Checking prerequisites..."
    
    if ! command_exists docker; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    print_success "Docker found"
    
    if ! command_exists docker-compose; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    print_success "Docker Compose found"
    
    if ! command_exists python3; then
        print_error "Python 3 is not installed. Please install Python 3.11+ first."
        exit 1
    fi
    print_success "Python 3 found"
    
    # Create necessary directories
    print_info "Creating directories..."
    mkdir -p data
    mkdir -p logs
    mkdir -p backups
    print_success "Directories created"
    
    # Create .env file if it doesn't exist
    if [ ! -f .env ]; then
        print_info "Creating .env file from .env.example..."
        cp .env.example .env
        print_success ".env file created"
        print_warning "Please review and update .env file with your configuration"
    else
        print_info ".env file already exists"
    fi
    
    # Install Python dependencies
    print_info "Installing Python dependencies..."
    if command_exists pip3; then
        pip3 install -r requirements.txt
    elif command_exists pip; then
        pip install -r requirements.txt
    else
        print_error "pip not found. Please install pip first."
        exit 1
    fi
    print_success "Python dependencies installed"
    
    # Build Docker images
    print_info "Building Docker images..."
    docker-compose build
    print_success "Docker images built"
    
    # Start services
    print_info "Starting services..."
    docker-compose up -d
    print_success "Services started"
    
    # Wait for services to be ready
    print_info "Waiting for services to be ready..."
    sleep 10
    
    # Check service health
    print_info "Checking service health..."
    max_retries=30
    retry_count=0
    
    while [ $retry_count -lt $max_retries ]; do
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            print_success "API is healthy"
            break
        fi
        
        retry_count=$((retry_count + 1))
        if [ $retry_count -eq $max_retries ]; then
            print_error "API failed to start"
            print_info "Check logs with: docker-compose logs api"
            exit 1
        fi
        
        echo -n "."
        sleep 2
    done
    
    # Seed database
    read -p "Do you want to seed the database with test data? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Seeding database..."
        python3 seed_database.py
        print_success "Database seeded"
    fi
    
    # Display status
    print_header "Setup Complete!"
    echo ""
    print_success "All services are running:"
    echo ""
    docker-compose ps
    echo ""
    
    print_info "Service URLs:"
    echo "  🌐 API: http://localhost:8000"
    echo "  📚 API Docs: http://localhost:8000/docs"
    echo "  📖 ReDoc: http://localhost:8000/redoc"
    echo "  ❤️  Health: http://localhost:8000/health"
    echo ""
    
    print_info "Quick Commands:"
    echo "  📊 View logs: docker-compose logs -f"
    echo "  🛑 Stop services: docker-compose down"
    echo "  🔄 Restart: docker-compose restart"
    echo "  🧪 Load test: make load-test"
    echo "  📈 Monitor: make monitor"
    echo ""
    
    print_info "Test the API:"
    echo "  curl http://localhost:8000/health"
    echo "  curl http://localhost:8000/recommend/1"
    echo ""
    
    print_success "🚀 System is ready for use!"
}

# Run main function
main