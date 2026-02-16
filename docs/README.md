# VTrack Documentation

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
- [Troubleshooting](guides/troubleshooting.md) - Common issues and solutions

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
