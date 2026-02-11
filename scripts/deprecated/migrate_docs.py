#!/usr/bin/env python3
"""
Documentation Migration Script

Safely migrates documentation from flat structure to organized hierarchy.
- Creates new directory structure
- Copies files to new locations
- Updates all cross-references
- Creates index files
- Validates links
- Keeps old files for safety

Usage:
    python migrate_docs.py --dry-run    # See what would happen
    python migrate_docs.py              # Perform migration
    python migrate_docs.py --cleanup    # Remove old files after verification
"""

import os
import re
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Color codes for output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_step(msg):
    print(f"{Colors.BLUE}{Colors.BOLD}▶ {msg}{Colors.RESET}")

def print_success(msg):
    print(f"{Colors.GREEN}✓ {msg}{Colors.RESET}")

def print_warning(msg):
    print(f"{Colors.YELLOW}⚠ {msg}{Colors.RESET}")

def print_error(msg):
    print(f"{Colors.RED}✗ {msg}{Colors.RESET}")

def print_info(msg):
    print(f"{Colors.CYAN}  {msg}{Colors.RESET}")

# Migration mapping: old_path -> new_path
MIGRATION_MAP = {
    'ARCHITECTURE_OVERVIEW.md': 'docs/architecture/overview.md',
    'MICROSERVICES_GUIDE.md': 'docs/architecture/microservices.md',
    'MICROSERVICES_README.md': 'docs/architecture/quick-reference.md',

    'DEV_WORKFLOW.md': 'docs/guides/development/workflow.md',
    'ALERT_PROCESSOR_GUIDE.md': 'docs/guides/alert-processor.md',
    'REDIS_QUEUE_GUIDE.md': 'docs/guides/redis/queue-guide.md',
    'REDIS_QUICK_REFERENCE.md': 'docs/guides/redis/quick-reference.md',
    'DEPLOYMENT_GUIDE.md': 'docs/guides/deployment.md',
    'ALEMBIC_GUIDE.md': 'docs/guides/database-migrations.md',

    'TESTING_GUIDE.md': 'docs/testing/guide.md',
    'TEST_COMMANDS.md': 'docs/testing/commands.md',

    'MICROSERVICES_RESTRUCTURE_SUMMARY.md': 'docs/archive/restructure-summary.md',
    'MICROSERVICES_TEST_SUITE.md': 'docs/archive/test-suite.md',
    'TEST_SUITE_SUMMARY.md': 'docs/archive/test-suite-summary.md',
    'TESTING_ROADMAP.md': 'docs/archive/testing-roadmap.md',
    'MIGRATIONS_README.md': 'docs/archive/migrations-readme.md',
}

class DocsMigration:
    def __init__(self, root_dir: str, dry_run: bool = False):
        self.root = Path(root_dir)
        self.dry_run = dry_run
        self.reverse_map = {v: k for k, v in MIGRATION_MAP.items()}

    def create_directory_structure(self):
        """Create the new directory structure"""
        print_step("Creating directory structure")

        dirs = [
            'docs',
            'docs/getting-started',
            'docs/architecture',
            'docs/guides',
            'docs/guides/development',
            'docs/guides/redis',
            'docs/testing',
            'docs/archive',
        ]

        for dir_path in dirs:
            full_path = self.root / dir_path
            if self.dry_run:
                print_info(f"Would create: {dir_path}")
            else:
                full_path.mkdir(parents=True, exist_ok=True)
                print_success(f"Created: {dir_path}")

    def copy_files(self):
        """Copy files to new locations"""
        print_step("Copying documentation files")

        for old_path, new_path in MIGRATION_MAP.items():
            old_file = self.root / old_path
            new_file = self.root / new_path

            if not old_file.exists():
                print_warning(f"Source not found: {old_path}")
                continue

            if self.dry_run:
                print_info(f"Would copy: {old_path} → {new_path}")
            else:
                shutil.copy2(old_file, new_file)
                print_success(f"Copied: {old_path} → {new_path}")

    def update_cross_references(self):
        """Update all cross-references in documentation files"""
        print_step("Updating cross-references")

        # Patterns to match markdown links
        patterns = [
            r'\[([^\]]+)\]\(\.?/?([^)]+\.md)\)',  # [text](./file.md) or [text](file.md)
            r'\[([^\]]+)\]\(\.?/([^)]+\.md)#([^)]+)\)',  # [text](file.md#anchor)
        ]

        new_docs = list(self.root.glob('docs/**/*.md'))

        for doc_file in new_docs:
            if self.dry_run:
                print_info(f"Would update references in: {doc_file.relative_to(self.root)}")
                continue

            content = doc_file.read_text()
            original_content = content

            # Update each old path reference to new path
            for old_path, new_path in MIGRATION_MAP.items():
                # Calculate relative path from current doc to new location
                current_dir = doc_file.parent
                target_file = self.root / new_path

                try:
                    rel_path = os.path.relpath(target_file, current_dir)

                    # Replace various forms of the old path
                    patterns_to_replace = [
                        (f'](./{old_path})', f']({rel_path})'),
                        (f']({old_path})', f']({rel_path})'),
                        (f'](../{old_path})', f']({rel_path})'),
                        (f'](./{old_path.replace(".md", "")})', f']({rel_path})'),
                    ]

                    for old_pattern, new_pattern in patterns_to_replace:
                        if old_pattern in content:
                            content = content.replace(old_pattern, new_pattern)

                except ValueError:
                    pass  # Can't calculate relative path

            # Write back if changed
            if content != original_content:
                doc_file.write_text(content)
                print_success(f"Updated references in: {doc_file.relative_to(self.root)}")

    def create_main_readme(self):
        """Create main README.md"""
        print_step("Creating main README.md")

        readme_content = """# VTrack - Vehicle Tracking System

Real-time coordinate tracking and geofence alerting microservices system.

## 🚀 Quick Start

```bash
# Start all services
docker-compose up -d

# View status
docker ps

# View logs
docker logs -f alert_processor
```

See [Quick Start Guide](docs/getting-started/quickstart.md) for detailed setup.

## 📚 Documentation

Complete documentation is in the [`docs/`](docs/) directory:

- **[Getting Started](docs/getting-started/)** - Installation and quick start
- **[Architecture](docs/architecture/)** - System design and architecture
- **[Development Guides](docs/guides/)** - How-to guides for development
- **[Testing](docs/testing/)** - Testing procedures and commands

See [**docs/README.md**](docs/README.md) for complete documentation index.

## ✨ Features

- 🗺️ Real-time GPS coordinate tracking
- 🚨 Geofence entry/exit alerts
- 🔄 Redis-based message queues
- 🐳 Microservices architecture with Docker
- 📊 PostgreSQL data persistence
- ⚡ Scalable alert processing
- 🛠️ Development tools (monitoring, testing)

## 🏗️ Architecture

```
FastAPI (Producer) → Redis Queues → Alert Processor (Consumer)
                          ↓
                   PostgreSQL DB
```

See [Architecture Overview](docs/architecture/overview.md) for details.

## 🛠️ Development

### Monitor Queues
```bash
python redis_monitor.py --interval 1
```

### Test Alert Processor
```bash
python test_alert_processor.py --scenario zone
```

### Hot Reload Development
```bash
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

See [Development Workflow](docs/guides/development/workflow.md) for more.

## 📖 Documentation Structure

```
docs/
├── getting-started/        # Quick start and installation
├── architecture/           # System design and architecture
├── guides/                 # Development, deployment, Redis
├── testing/                # Testing procedures
└── archive/                # Historical documentation
```

## 🧪 Testing

```bash
# Run tests
pytest app/tests/

# Test alert processor
python test_alert_processor.py --load 100

# Monitor Redis
python redis_monitor.py
```

See [Testing Guide](docs/testing/guide.md) for details.

## 🚢 Deployment

See [Deployment Guide](docs/guides/deployment.md) for production deployment.

## 📝 License

[Your License Here]

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

**Version:** 1.0
**Last Updated:** February 2026
**Architecture:** Microservices + Redis Queues
"""

        readme_file = self.root / 'README.md'

        if self.dry_run:
            print_info("Would create: README.md")
        else:
            # Backup existing README if it exists
            if readme_file.exists():
                backup = self.root / 'README.md.backup'
                shutil.copy2(readme_file, backup)
                print_warning(f"Backed up existing README.md to README.md.backup")

            readme_file.write_text(readme_content)
            print_success("Created: README.md")

    def create_docs_index(self):
        """Create docs/README.md index"""
        print_step("Creating docs/README.md index")

        index_content = """# VTrack Documentation

Complete documentation for the VTrack vehicle tracking system.

## 📖 Documentation Index

### 🚀 Getting Started
- [Quick Start Guide](getting-started/quickstart.md) - Get up and running in 5 minutes
- [Installation Guide](getting-started/installation.md) - Detailed installation instructions

### 🏗️ Architecture
- [System Overview](architecture/overview.md) - Complete visual architecture guide
- [Microservices Architecture](architecture/microservices.md) - Microservices design and communication
- [Quick Reference](architecture/quick-reference.md) - Quick start and common commands

### 📚 Development Guides

#### General
- [Alert Processor](guides/alert-processor.md) - How the consumer works
- [Database Migrations](guides/database-migrations.md) - Alembic migrations guide
- [Deployment](guides/deployment.md) - Production deployment guide

#### Development
- [Development Workflow](guides/development/workflow.md) - Development best practices and hot reload

#### Redis Queues
- [Redis Queue Guide](guides/redis/queue-guide.md) - Complete Redis queue documentation
- [Redis Quick Reference](guides/redis/quick-reference.md) - Redis command cheat sheet

### 🧪 Testing
- [Testing Guide](testing/guide.md) - Testing procedures and strategies
- [Test Commands](testing/commands.md) - Quick reference for test commands

### 📦 Archive
- [Restructure Summary](archive/restructure-summary.md) - Microservices restructure documentation
- [Test Suite Summary](archive/test-suite-summary.md) - Historical test suite information

## 🛠️ Development Tools

Available in the root directory:

- **redis_monitor.py** - Real-time queue monitoring
  ```bash
  python redis_monitor.py --interval 1
  ```

- **test_alert_processor.py** - Testing tool
  ```bash
  python test_alert_processor.py --scenario zone
  ```

- **docker-compose.dev.yml** - Hot reload configuration
  ```bash
  docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
  ```

## 📋 Quick Links

### Most Used Docs
1. [Development Workflow](guides/development/workflow.md) - Start here for development
2. [Redis Queue Guide](guides/redis/queue-guide.md) - Understanding the message queue
3. [System Overview](architecture/overview.md) - Understanding the architecture
4. [Alert Processor](guides/alert-processor.md) - Understanding the consumer

### Quick Commands
```bash
# Monitor queues
python redis_monitor.py

# Test system
python test_alert_processor.py --scenario zone

# View logs
docker logs -f alert_processor

# Restart consumer
docker restart alert_processor
```

## 📚 Learning Path

### For New Users
1. Read [Quick Start](getting-started/quickstart.md)
2. Read [System Overview](architecture/overview.md)
3. Try [Redis Quick Reference](guides/redis/quick-reference.md)

### For Developers
1. Read [Development Workflow](guides/development/workflow.md)
2. Read [Alert Processor Guide](guides/alert-processor.md)
3. Read [Redis Queue Guide](guides/redis/queue-guide.md)
4. Read [Testing Guide](testing/guide.md)

### For DevOps
1. Read [Microservices Architecture](architecture/microservices.md)
2. Read [Deployment Guide](guides/deployment.md)
3. Read [Database Migrations](guides/database-migrations.md)

## 🔍 Finding Documentation

- **Architecture Questions?** → [architecture/](architecture/)
- **How do I...?** → [guides/](guides/)
- **Testing?** → [testing/](testing/)
- **Getting Started?** → [getting-started/](getting-started/)

---

**Tip:** Use your editor's file search (Ctrl+P in VS Code) to quickly find documentation files!
"""

        index_file = self.root / 'docs' / 'README.md'

        if self.dry_run:
            print_info("Would create: docs/README.md")
        else:
            index_file.write_text(index_content)
            print_success("Created: docs/README.md")

    def create_quickstart(self):
        """Create getting-started/quickstart.md"""
        print_step("Creating quick start guide")

        quickstart_content = """# Quick Start Guide

Get VTrack up and running in 5 minutes.

## Prerequisites

- Docker & Docker Compose
- Git
- Python 3.11+ (for development tools)

## 1. Clone and Setup

```bash
# Clone repository
git clone <your-repo-url>
cd vtrack

# Copy environment file
cp .env.example .env

# Edit .env with your credentials
vim .env
```

## 2. Start Services

```bash
# Start all services
docker-compose up -d

# Check status
docker ps

# Should see:
# - postgres_db
# - redis_queue
# - fastapi_api
# - alert_processor
```

## 3. Verify Setup

```bash
# Check API health
curl http://localhost:8000/docs

# Check Redis
docker exec redis_queue redis-cli ping

# Check alert processor logs
docker logs alert_processor
```

## 4. Start Data Collection

```bash
# Start scraping
curl -X POST http://localhost:8000/collection/start

# Check status
curl http://localhost:8000/collection/status
```

## 5. Monitor the System

### Terminal 1: Monitor Queues
```bash
python redis_monitor.py --interval 1
```

### Terminal 2: Watch Consumer
```bash
docker logs -f alert_processor
```

### Terminal 3: Test
```bash
python test_alert_processor.py --scenario zone
```

## 🎉 Success!

You should now see:
- Coordinates being scraped and queued
- Alert processor consuming coordinates
- Alerts being generated for geofence entries

## Next Steps

1. Read [Architecture Overview](../architecture/overview.md)
2. Try [Development Workflow](../guides/development/workflow.md)
3. Explore [Redis Queue Guide](../guides/redis/queue-guide.md)

## Troubleshooting

### Services not starting?
```bash
docker-compose down
docker-compose up -d
docker-compose logs
```

### Can't connect to database?
Check DATABASE_URL in .env file

### Redis issues?
```bash
docker restart redis_queue
```

See [Microservices Guide](../architecture/microservices.md) for detailed troubleshooting.
"""

        quickstart_file = self.root / 'docs' / 'getting-started' / 'quickstart.md'

        if self.dry_run:
            print_info("Would create: docs/getting-started/quickstart.md")
        else:
            quickstart_file.write_text(quickstart_content)
            print_success("Created: docs/getting-started/quickstart.md")

    def validate_links(self):
        """Validate all internal links in documentation"""
        print_step("Validating internal links")

        all_docs = list(self.root.glob('docs/**/*.md'))
        broken_links = []

        for doc_file in all_docs:
            content = doc_file.read_text()
            current_dir = doc_file.parent

            # Find all markdown links
            links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', content)

            for link_text, link_path in links:
                # Skip external links
                if link_path.startswith('http://') or link_path.startswith('https://'):
                    continue

                # Skip anchors
                if link_path.startswith('#'):
                    continue

                # Remove anchor if present
                link_path = link_path.split('#')[0]

                # Resolve relative path
                target_path = (current_dir / link_path).resolve()

                if not target_path.exists():
                    broken_links.append((doc_file.relative_to(self.root), link_path))

        if broken_links:
            print_warning(f"Found {len(broken_links)} broken links:")
            for doc, link in broken_links:
                print_info(f"  {doc} → {link}")
            return False
        else:
            print_success("All links valid!")
            return True

    def create_old_files_notice(self):
        """Create a notice file in root for old .md files"""
        print_step("Creating notice for old files")

        notice_content = """# Old Documentation Files

⚠️ **These files have been migrated to the `docs/` directory.**

## Migration Complete

All documentation has been reorganized into a clean structure under `docs/`.

### Where to Find Documentation

- **Main Entry:** [README.md](README.md)
- **Documentation Index:** [docs/README.md](docs/README.md)
- **Architecture:** [docs/architecture/](docs/architecture/)
- **Guides:** [docs/guides/](docs/guides/)
- **Testing:** [docs/testing/](docs/testing/)

### Old Files (Safe to Delete)

The following files in the root directory are now redundant:

"""

        for old_file in MIGRATION_MAP.keys():
            notice_content += f"- {old_file}\n"

        notice_content += """
### To Clean Up

```bash
# Review the new structure first
ls -la docs/

# Then run cleanup
python migrate_docs.py --cleanup
```

Or manually delete old files:
```bash
"""

        for old_file in MIGRATION_MAP.keys():
            notice_content += f"rm {old_file}\n"

        notice_content += "```\n"

        notice_file = self.root / 'OLD_DOCS_README.md'

        if self.dry_run:
            print_info("Would create: OLD_DOCS_README.md")
        else:
            notice_file.write_text(notice_content)
            print_success("Created: OLD_DOCS_README.md")

    def cleanup_old_files(self):
        """Remove old documentation files from root"""
        print_step("Cleaning up old files")

        for old_file in MIGRATION_MAP.keys():
            file_path = self.root / old_file

            if not file_path.exists():
                continue

            if self.dry_run:
                print_info(f"Would delete: {old_file}")
            else:
                file_path.unlink()
                print_success(f"Deleted: {old_file}")

        # Also remove the proposal file
        proposal = self.root / 'DOCS_STRUCTURE_PROPOSAL.md'
        if proposal.exists():
            if self.dry_run:
                print_info("Would delete: DOCS_STRUCTURE_PROPOSAL.md")
            else:
                proposal.unlink()
                print_success("Deleted: DOCS_STRUCTURE_PROPOSAL.md")

    def run(self, cleanup=False):
        """Run the full migration"""
        print(f"\n{Colors.BOLD}{'='*70}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}VTrack Documentation Migration{Colors.RESET}")
        print(f"{Colors.BOLD}{'='*70}{Colors.RESET}\n")

        if self.dry_run:
            print_warning("DRY RUN MODE - No changes will be made\n")

        if cleanup:
            response = input(f"{Colors.YELLOW}This will DELETE old documentation files. Continue? (yes/no): {Colors.RESET}")
            if response.lower() != 'yes':
                print_error("Cleanup cancelled")
                return False

            self.cleanup_old_files()
            print(f"\n{Colors.GREEN}{Colors.BOLD}✓ Cleanup complete!{Colors.RESET}\n")
            return True

        # Normal migration
        self.create_directory_structure()
        self.copy_files()
        self.update_cross_references()
        self.create_main_readme()
        self.create_docs_index()
        self.create_quickstart()
        self.create_old_files_notice()

        print("\n")
        self.validate_links()

        print(f"\n{Colors.BOLD}{'='*70}{Colors.RESET}")
        print(f"{Colors.GREEN}{Colors.BOLD}✓ Migration Complete!{Colors.RESET}")
        print(f"{Colors.BOLD}{'='*70}{Colors.RESET}\n")

        if not self.dry_run:
            print_info("Next steps:")
            print_info("1. Review the new structure: ls -la docs/")
            print_info("2. Check the main README: cat README.md")
            print_info("3. Browse docs index: cat docs/README.md")
            print_info("4. Verify everything works")
            print_info("5. Run cleanup: python migrate_docs.py --cleanup")

        return True

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Migrate VTrack documentation')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without making changes')
    parser.add_argument('--cleanup', action='store_true',
                       help='Remove old documentation files (after verification)')

    args = parser.parse_args()

    root_dir = Path(__file__).parent
    migration = DocsMigration(root_dir, dry_run=args.dry_run)

    try:
        migration.run(cleanup=args.cleanup)
    except Exception as e:
        print_error(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
