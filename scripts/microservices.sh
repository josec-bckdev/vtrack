#!/bin/bash

# VTrack Microservices Quick Start Script
# This script helps with common microservices operations

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Function to display usage
show_usage() {
    cat << EOF
${BLUE}VTrack Microservices Management${NC}

Usage: ./scripts/microservices.sh [COMMAND] [OPTIONS]

Commands:
  start                 Start all services (dev convenience)
  conductor-start       Production start: create containers, start conductor only
  stop                  Stop all services
  restart              Restart all services
  logs [SERVICE]       Show logs (optionally for a specific service)
  status               Show status of all services
  build                Build all microservice images
  rebuild              Clean build all microservice images
  scale-alerts         Scale alert processor (requires argument: number)
  health               Check health of all services
  install-shared       Install/update the shared package
  queue-stats          Show Redis queue statistics
  clean                Remove all containers and volumes

Service names:
  - conductor         Container lifecycle manager (always-on, restart: always)
  - api               FastAPI application        (conductor-managed, restart: no)
  - alert-processor   Alert processing           (conductor-managed, restart: no)
  - notification-sender Telegram notifications  (conductor-managed, restart: no)
  - db                PostgreSQL database        (conductor-managed, restart: no)
  - redis             Redis message queue        (conductor-managed, restart: no)
  - pgadmin           PGAdmin interface          (unmanaged admin tool)
  - migrate           Migration service          (one-shot, run manually)

Examples:
  ./scripts/microservices.sh conductor-start
  ./scripts/microservices.sh logs conductor
  ./scripts/microservices.sh logs api
  ./scripts/microservices.sh logs alert-processor
  ./scripts/microservices.sh scale-alerts 3
  ./scripts/microservices.sh queue-stats
  
EOF
    exit 1
}

# Function to start services (dev convenience — starts everything)
start_services() {
    print_header "Starting VTrack Microservices (dev mode)"
    print_warning "In production use 'conductor-start' instead — conductor manages the stack lifecycle"
    docker compose up -d
    print_success "Services started"

    # Wait for services to be ready
    print_header "Waiting for services to be healthy"
    sleep 5

    health_check
}

# Function to start conductor only (production mode)
conductor_start() {
    print_header "Starting conductor (production mode)"
    docker compose up --no-start
    docker compose up -d conductor
    print_success "Conductor started — it will bring up managed containers at the next window_open"
    echo ""
    print_warning "Follow conductor logs: ./scripts/microservices.sh logs conductor"
}

# Function to stop services
stop_services() {
    print_header "Stopping VTrack Microservices"
    docker compose down
    print_success "Services stopped"
}

# Function to restart services
restart_services() {
    print_header "Restarting VTrack Microservices"
    docker compose restart
    print_success "Services restarted"
}

# Function to show logs
show_logs() {
    if [ -z "$1" ]; then
        print_header "Showing logs for all services (press Ctrl+C to exit)"
        docker compose logs -f
    else
        print_header "Showing logs for service: $1"
        docker compose logs -f "$1"
    fi
}

# Function to show status
show_status() {
    print_header "Service Status"
    docker compose ps
}

# Function to build images
build_images() {
    print_header "Building microservice images"
    docker compose build
    print_success "Images built successfully"
}

# Function to rebuild images
rebuild_images() {
    print_header "Rebuilding microservice images (clean)"
    docker compose build --no-cache
    print_success "Images rebuilt successfully"
}

# Function to scale alert processor
scale_alerts() {
    if [ -z "$1" ]; then
        print_error "Please specify number of replicas: ./scripts/microservices.sh scale-alerts 3"
        exit 1
    fi
    
    print_header "Scaling alert-processor to $1 instances"
    # Note: Docker Compose doesn't support scaling in the same way as Docker Swarm
    # This is a note for future implementation
    print_warning "Note: Docker Compose scaling requires docker compose up -d --scale alert-processor=$1"
    print_warning "Manual scaling is recommended for microservices architecture"
    exit 1
}

# Function to check health
health_check() {
    print_header "Checking service health"

    # Check Conductor (always-on)
    if docker ps --filter "name=conductor" --filter "status=running" | grep -q conductor; then
        print_success "Conductor is running"
    else
        print_error "Conductor is not running (start with: docker compose up -d conductor)"
    fi

    # Check PostgreSQL
    if docker exec postgres_db psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -c "SELECT 1" > /dev/null 2>&1; then
        print_success "PostgreSQL is healthy"
    else
        print_warning "PostgreSQL is not responding (conductor will start it at next window_open)"
    fi

    # Check Redis
    if docker exec redis_queue redis-cli ping > /dev/null 2>&1; then
        print_success "Redis is healthy"
    else
        print_warning "Redis is not responding (conductor will start it at next window_open)"
    fi

    # Check API
    if curl -s http://localhost:8000/monitor/health > /dev/null 2>&1; then
        print_success "FastAPI is responding"
    else
        print_warning "FastAPI is not responding (conductor will start it at next window_open)"
    fi

    # Check Alert Processor
    if docker ps --filter "name=alert_processor" --filter "status=running" | grep -q alert_processor; then
        if docker exec alert_processor pgrep -f "main.py" > /dev/null 2>&1; then
            print_success "Alert Processor is running"
        else
            print_error "Alert Processor process not found inside container"
        fi
    else
        print_warning "Alert Processor is not running (conductor will start it at next window_open)"
    fi

    # Check Notification Sender
    if docker ps --filter "name=notification_sender" --filter "status=running" | grep -q notification_sender; then
        print_success "Notification Sender is running"
    else
        print_warning "Notification Sender is not running (conductor will start it at next window_open)"
    fi
}

# Function to show queue statistics
queue_stats() {
    print_header "Redis Queue Statistics"
    
    # Check if redis container is running
    if ! docker ps | grep -q redis_queue; then
        print_error "Redis container is not running"
        exit 1
    fi
    
    echo "Coordinate Queue Length:"
    docker exec redis_queue redis-cli LLEN coordinate_queue
    
    echo ""
    echo "Alert Queue Length:"
    docker exec redis_queue redis-cli LLEN alert_queue
    
    echo ""
    echo "Redis Memory Usage:"
    docker exec redis_queue redis-cli INFO memory | grep used_memory_human
    
    echo ""
    print_success "Queue statistics retrieved"
}

# Function to install shared package
install_shared() {
    print_header "Installing shared package"
    
    if [ ! -d "shared-package" ]; then
        print_error "shared-package directory not found"
        exit 1
    fi
    
    pip install -e ./shared-package
    print_success "Shared package installed"
}

# Function to clean up
clean_system() {
    print_header "Cleaning VTrack system"
    print_warning "This will remove all containers and volumes!"
    
    read -p "Are you sure? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        print_warning "Cleanup cancelled"
        exit 0
    fi
    
    docker compose down -v
    print_success "System cleaned"
}

# Main script logic
case "$1" in
    start)
        start_services
        ;;
    conductor-start)
        conductor_start
        ;;
    stop)
        stop_services
        ;;
    restart)
        restart_services
        ;;
    logs)
        show_logs "$2"
        ;;
    status)
        show_status
        ;;
    build)
        build_images
        ;;
    rebuild)
        rebuild_images
        ;;
    scale-alerts)
        scale_alerts "$2"
        ;;
    health)
        health_check
        ;;
    install-shared)
        install_shared
        ;;
    queue-stats)
        queue_stats
        ;;
    clean)
        clean_system
        ;;
    *)
        show_usage
        ;;
esac
