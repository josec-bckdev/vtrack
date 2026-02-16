# VTrack - Vehicle Tracking System

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

## � Troubleshooting

Having issues? Check the [Troubleshooting Guide](docs/guides/troubleshooting.md) for:
- ContainerConfig errors
- Clean slate procedures
- Database backup/restore
- Common Docker issues

**Quick fixes:**
```bash
# Service not responding
docker-compose restart <service>

# Container issues
docker-compose down && docker-compose up -d

# Complete reset (⚠️ BACKUP FIRST!)
docker-compose down -v && docker-compose up -d --build
```

## �🚢 Deployment

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
