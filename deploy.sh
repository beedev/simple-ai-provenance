#!/bin/bash

# MCP AI Commit Deployment Script
# Supports local development, staging, and production deployments

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="mcp-ai-commit"
DEFAULT_ENV="development"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored output
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

# Usage information
show_usage() {
    cat << EOF
Usage: $0 [ENVIRONMENT] [OPTIONS]

ENVIRONMENTS:
  development  - Local development setup (default)
  staging      - Staging environment with shared database
  production   - Production deployment with full security

OPTIONS:
  --build-only     Build Docker images without starting services
  --no-cache       Build Docker images without cache
  --reset-db       Reset database (WARNING: destroys all data)
  --logs           Show logs after deployment
  --help           Show this help message

EXAMPLES:
  $0                           # Deploy development environment
  $0 production                # Deploy production environment
  $0 staging --reset-db        # Deploy staging with database reset
  $0 development --logs        # Deploy development and show logs

PREREQUISITES:
  - Docker and Docker Compose installed
  - .env file configured (copy from .env.example)
  - For production: proper API keys and secure passwords set

EOF
}

# Parse command line arguments
ENVIRONMENT="${1:-$DEFAULT_ENV}"
BUILD_ONLY=false
NO_CACHE=false
RESET_DB=false
SHOW_LOGS=false

shift || true
while [[ $# -gt 0 ]]; do
    case $1 in
        --build-only)
            BUILD_ONLY=true
            shift
            ;;
        --no-cache)
            NO_CACHE=true
            shift
            ;;
        --reset-db)
            RESET_DB=true
            shift
            ;;
        --logs)
            SHOW_LOGS=true
            shift
            ;;
        --help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Validate environment
case $ENVIRONMENT in
    development|staging|production)
        ;;
    *)
        print_error "Invalid environment: $ENVIRONMENT"
        print_error "Must be one of: development, staging, production"
        exit 1
        ;;
esac

print_status "Deploying MCP AI Commit - Environment: $ENVIRONMENT"

# Change to script directory
cd "$SCRIPT_DIR"

# Check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        exit 1
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        print_error "Docker Compose is not installed"
        exit 1
    fi
    
    # Check .env file
    if [[ ! -f .env ]]; then
        print_warning ".env file not found, copying from .env.example"
        if [[ -f .env.example ]]; then
            cp .env.example .env
            print_warning "Please edit .env file with your configuration before proceeding"
            if [[ "$ENVIRONMENT" == "production" ]]; then
                print_error "Production deployment requires properly configured .env file"
                exit 1
            fi
        else
            print_error ".env.example not found"
            exit 1
        fi
    fi
    
    print_success "Prerequisites check passed"
}

# Validate configuration for environment
validate_config() {
    print_status "Validating configuration for $ENVIRONMENT environment..."
    
    source .env 2>/dev/null || true
    
    case $ENVIRONMENT in
        production)
            # Production validation
            if [[ -z "$OPENAI_API_KEY" ]] || [[ "$OPENAI_API_KEY" == "your-key-here" ]]; then
                print_error "Production requires valid OPENAI_API_KEY in .env"
                exit 1
            fi
            
            if [[ -z "$POSTGRES_PASSWORD" ]] || [[ "$POSTGRES_PASSWORD" == "your_password_here" ]]; then
                print_error "Production requires secure POSTGRES_PASSWORD in .env"
                exit 1
            fi
            
            print_success "Production configuration validated"
            ;;
        staging)
            # Staging validation
            if [[ -z "$OPENAI_API_KEY" ]]; then
                print_warning "OPENAI_API_KEY not set - AI features will not work"
            fi
            print_success "Staging configuration validated"
            ;;
        development)
            # Development validation (lenient)
            if [[ -z "$OPENAI_API_KEY" ]]; then
                print_warning "OPENAI_API_KEY not set - some features may not work"
            fi
            print_success "Development configuration validated"
            ;;
    esac
}

# Set environment-specific configurations
configure_environment() {
    print_status "Configuring for $ENVIRONMENT environment..."
    
    # Copy environment-specific docker-compose override if it exists
    OVERRIDE_FILE="docker-compose.$ENVIRONMENT.yml"
    if [[ -f "$OVERRIDE_FILE" ]]; then
        export COMPOSE_FILE="docker-compose.yml:$OVERRIDE_FILE"
        print_status "Using override file: $OVERRIDE_FILE"
    fi
    
    # Set environment variables
    export ENVIRONMENT="$ENVIRONMENT"
    
    case $ENVIRONMENT in
        production)
            export AI_COMMIT_LOG_LEVEL=WARNING
            export AI_COMMIT_VALIDATION_LEVEL=strict
            export AI_COMMIT_MAX_CONCURRENT=20
            ;;
        staging)
            export AI_COMMIT_LOG_LEVEL=INFO
            export AI_COMMIT_VALIDATION_LEVEL=strict
            export AI_COMMIT_MAX_CONCURRENT=10
            ;;
        development)
            export AI_COMMIT_LOG_LEVEL=DEBUG
            export AI_COMMIT_VALIDATION_LEVEL=warn
            export AI_COMMIT_MAX_CONCURRENT=5
            ;;
    esac
    
    print_success "Environment configured"
}

# Reset database if requested
reset_database() {
    if [[ "$RESET_DB" == true ]]; then
        print_warning "Resetting database - ALL DATA WILL BE LOST!"
        read -p "Are you sure? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_status "Stopping services..."
            docker-compose down -v 2>/dev/null || true
            
            print_status "Removing database volumes..."
            docker volume rm "${PROJECT_NAME}_postgres_data" 2>/dev/null || true
            docker volume rm "${PROJECT_NAME}_redis_data" 2>/dev/null || true
            
            print_success "Database reset complete"
        else
            print_status "Database reset cancelled"
        fi
    fi
}

# Build Docker images
build_images() {
    print_status "Building Docker images..."
    
    BUILD_ARGS=()
    if [[ "$NO_CACHE" == true ]]; then
        BUILD_ARGS+=(--no-cache)
        print_status "Building without cache"
    fi
    
    docker-compose build "${BUILD_ARGS[@]}"
    print_success "Docker images built successfully"
}

# Start services
start_services() {
    if [[ "$BUILD_ONLY" == true ]]; then
        print_success "Build-only mode - services not started"
        return
    fi
    
    print_status "Starting services..."
    
    # Start database services first
    print_status "Starting database services..."
    docker-compose up -d postgres redis
    
    # Wait for database to be ready
    print_status "Waiting for database to be ready..."
    timeout=60
    while ! docker-compose exec -T postgres pg_isready -U ai_commit_user -d ai_commit > /dev/null 2>&1; do
        if [[ $timeout -le 0 ]]; then
            print_error "Database failed to start within 60 seconds"
            docker-compose logs postgres
            exit 1
        fi
        sleep 2
        timeout=$((timeout-2))
        echo -n "."
    done
    echo
    print_success "Database is ready"
    
    # Start application services
    print_status "Starting application services..."
    docker-compose up -d
    
    # Wait for application to be ready
    print_status "Waiting for application to be ready..."
    timeout=60
    while ! docker-compose exec -T mcp-ai-commit python -c "import asyncio; from mcp_ai_commit.database import get_database; asyncio.run(get_database())" > /dev/null 2>&1; do
        if [[ $timeout -le 0 ]]; then
            print_error "Application failed to start within 60 seconds"
            docker-compose logs mcp-ai-commit
            exit 1
        fi
        sleep 2
        timeout=$((timeout-2))
        echo -n "."
    done
    echo
    print_success "Application is ready"
}

# Show deployment status
show_status() {
    print_status "Deployment status:"
    docker-compose ps
    
    echo
    print_status "Service URLs:"
    echo "  MCP AI Commit Server: http://localhost:8080"
    echo "  PostgreSQL Database: localhost:5432"
    echo "  Redis Cache: localhost:6379"
    
    echo
    print_status "Useful commands:"
    echo "  View logs: docker-compose logs -f"
    echo "  Stop services: docker-compose down"
    echo "  Restart: docker-compose restart"
    echo "  Shell access: docker-compose exec mcp-ai-commit bash"
    echo "  Database access: docker-compose exec postgres psql -U ai_commit_user -d ai_commit"
}

# Show logs if requested
show_logs_if_requested() {
    if [[ "$SHOW_LOGS" == true ]]; then
        print_status "Showing logs (Ctrl+C to exit)..."
        docker-compose logs -f
    fi
}

# Main deployment flow
main() {
    check_prerequisites
    validate_config
    configure_environment
    reset_database
    build_images
    start_services
    
    if [[ "$BUILD_ONLY" != true ]]; then
        show_status
        show_logs_if_requested
    fi
    
    print_success "Deployment complete!"
}

# Run main function
main "$@"