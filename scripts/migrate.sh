#!/bin/bash
# Alembic Migration Helper Script for Docker
# Usage: ./migrate.sh [command]

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CONTAINER_NAME="fastapi_api"

# Helper function to check if container is running
check_container() {
    if ! docker compose ps | grep -q "$CONTAINER_NAME.*Up"; then
        echo -e "${RED}Error: Container '$CONTAINER_NAME' is not running${NC}"
        echo "Start it with: docker compose up -d api"
        exit 1
    fi
}

# Helper function to print section headers
print_header() {
    echo -e "\n${BLUE}==>${NC} ${GREEN}$1${NC}\n"
}

# Show usage
show_help() {
    cat << EOF
${GREEN}Alembic Migration Helper${NC}

${YELLOW}Usage:${NC}
  ./migrate.sh [command]

${YELLOW}Commands:${NC}
  ${GREEN}upgrade${NC}       Apply all pending migrations (default)
  ${GREEN}current${NC}       Show current migration version
  ${GREEN}history${NC}       Show migration history
  ${GREEN}downgrade${NC}     Rollback one migration
  ${GREEN}create${NC}        Create a new migration (requires description)
  ${GREEN}status${NC}        Show detailed status
  ${GREEN}backup${NC}        Backup database before migration
  ${GREEN}help${NC}          Show this help message

${YELLOW}Examples:${NC}
  ./migrate.sh                     # Apply all migrations
  ./migrate.sh current             # Check current version
  ./migrate.sh create "add field"  # Create new migration
  ./migrate.sh backup              # Backup database

${YELLOW}Full Workflow:${NC}
  1. ./migrate.sh backup           # Backup first!
  2. ./migrate.sh current          # Check current state
  3. ./migrate.sh upgrade          # Apply migrations
  4. ./migrate.sh status           # Verify success

EOF
}

# Get current migration version
get_current() {
    print_header "Current Migration Version"
    check_container
    docker compose exec api alembic current
}

# Show migration history
show_history() {
    print_header "Migration History"
    check_container
    docker compose exec api alembic history --verbose
}

# Apply migrations
upgrade() {
    print_header "Applying Migrations"
    check_container

    echo -e "${YELLOW}Current version:${NC}"
    docker compose exec api alembic current
    echo ""

    echo -e "${YELLOW}Upgrading to latest...${NC}"
    docker compose exec api alembic upgrade head
    echo ""

    echo -e "${GREEN}✓ Migration complete!${NC}"
    echo -e "${YELLOW}New version:${NC}"
    docker compose exec api alembic current

    echo -e "\n${YELLOW}Restarting API to apply changes...${NC}"
    docker compose restart api
    echo -e "${GREEN}✓ API restarted${NC}"
}

# Rollback migration
downgrade() {
    print_header "Rolling Back Migration"
    check_container

    echo -e "${YELLOW}Current version:${NC}"
    docker compose exec api alembic current
    echo ""

    echo -e "${RED}⚠️  This will rollback ONE migration${NC}"
    read -p "Are you sure? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "Aborted."
        exit 0
    fi

    docker compose exec api alembic downgrade -1

    echo -e "\n${GREEN}✓ Rollback complete!${NC}"
    echo -e "${YELLOW}New version:${NC}"
    docker compose exec api alembic current
}

# Create new migration
create_migration() {
    print_header "Creating New Migration"
    check_container

    if [ -z "$1" ]; then
        echo -e "${RED}Error: Migration description required${NC}"
        echo "Usage: ./migrate.sh create \"description of changes\""
        exit 1
    fi

    echo -e "${YELLOW}Creating migration: $1${NC}"
    docker compose exec api alembic revision --autogenerate -m "$1"

    echo -e "\n${GREEN}✓ Migration created!${NC}"
    echo -e "${YELLOW}Remember to review the generated file in alembic/versions/${NC}"
}

# Show detailed status
show_status() {
    print_header "Migration Status"
    check_container

    echo -e "${YELLOW}Container Status:${NC}"
    docker compose ps api
    echo ""

    echo -e "${YELLOW}Current Migration:${NC}"
    docker compose exec api alembic current
    echo ""

    echo -e "${YELLOW}Migration History (last 5):${NC}"
    docker compose exec api alembic history -r-5:
    echo ""

    echo -e "${YELLOW}Database Connection:${NC}"
    docker compose exec api python -c "import os; print(f'DATABASE_URL: {os.environ.get(\"DATABASE_URL\", \"NOT SET\")}')"
}

# Backup database
backup_database() {
    print_header "Backing Up Database"

    # Get database credentials from environment
    DB_CONTAINER="postgres_db"
    BACKUP_DIR="./backups"
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_FILE="$BACKUP_DIR/backup_$TIMESTAMP.sql"

    # Create backup directory
    mkdir -p "$BACKUP_DIR"

    echo -e "${YELLOW}Creating backup: $BACKUP_FILE${NC}"

    # Use docker compose exec to run pg_dump
    docker compose exec -T db pg_dump -U user app_db > "$BACKUP_FILE"

    if [ -f "$BACKUP_FILE" ]; then
        BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
        echo -e "${GREEN}✓ Backup created successfully!${NC}"
        echo -e "  File: $BACKUP_FILE"
        echo -e "  Size: $BACKUP_SIZE"
    else
        echo -e "${RED}✗ Backup failed${NC}"
        exit 1
    fi
}

# Main command handler
case "${1:-upgrade}" in
    upgrade)
        upgrade
        ;;
    current)
        get_current
        ;;
    history)
        show_history
        ;;
    downgrade)
        downgrade
        ;;
    create)
        create_migration "$2"
        ;;
    status)
        show_status
        ;;
    backup)
        backup_database
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo -e "${RED}Error: Unknown command '$1'${NC}"
        echo "Run './migrate.sh help' for usage information"
        exit 1
        ;;
esac
