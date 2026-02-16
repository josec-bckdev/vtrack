# Quick Start Guide

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

### ContainerConfig errors or corrupted containers?
See the [Troubleshooting Guide](../guides/troubleshooting.md) for complete solutions.

**For comprehensive troubleshooting, including:**
- ContainerConfig error fixes
- Clean slate workflows
- Database backup/restore procedures
- Common Docker issues

👉 **[View Full Troubleshooting Guide](../guides/troubleshooting.md)**
