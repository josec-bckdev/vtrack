# VTrack Microservices Architecture - Summary

## What Changed?

The VTrack application has been restructured from a monolithic approach to a **microservices architecture**. This makes the system more scalable, maintainable, and easier to deploy independently.

## New Project Structure

```
vtrack/
├── app/                              # ✅ Main FastAPI Application (unchanged core)
│   ├── main.py                       # Updated to use shared package
│   ├── scraper_async.py             # Updated to push coords to Redis
│   ├── models.py
│   ├── database.py
│   ├── data_server.py
│   └── tests/
│
├── microservices/                    # 🆕 MICROSERVICES DIRECTORY
│   ├── alert-processor/              # 🆕 NEW: Alert Processing Service
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── main.py                   # Processes coordinates, generates alerts
│   │
│   └── data-collector/               # 🆕 NEW: Optional standalone collector
│       ├── Dockerfile
│       ├── requirements.txt
│       └── main.py                   # Future enhancement for distributed collection
│
├── shared-package/                   # 🆕 NEW: Shared Code Package
│   ├── setup.py
│   ├── pyproject.toml
│   └── src/shared/
│       ├── __init__.py
│       ├── message_queue.py          # 📦 Shared Redis communication
│       └── location_alerts.py        # 📦 Shared geofencing logic
│
├── scripts/                          # 🆕 NEW: Helper Scripts
│   └── microservices.sh              # 🆕 Microservices management CLI
│
├── docker-compose.yml                # ✅ Updated with microservices
├── Dockerfile                        # ✅ Updated to install shared package
├── requirements.txt                  # ✅ Updated with geopy
│
├── MICROSERVICES_GUIDE.md           # 🆕 Complete architecture guide
├── DEPLOYMENT_GUIDE.md              # 🆕 Production deployment guide
└── [existing files...]
```

## Key Improvements

### 1. **Separation of Concerns**
- **API Service**: Handles HTTP requests, data collection, scheduling
- **Alert Processor**: Handles geofencing analysis and alert generation
- **Shared Package**: Reusable code for all services

### 2. **Independent Scaling**
```bash
# Run multiple alert processors for higher throughput
docker-compose up -d --scale alert-processor=3
```

### 3. **Better Deployment**
- Each service has its own Dockerfile
- Shared code via Python package
- Services communicate via Redis (decoupled)
- Easy to deploy on Kubernetes or Docker Swarm

### 4. **Resilience**
- Services are independent - failure in one doesn't crash others
- Asynchronous message queue prevents data loss
- Each service can be restarted independently

## How It Works

```
┌──────────────────┐
│   FastAPI App    │
│   (Port 8000)    │  Collects data from remote API
└────────┬─────────┘  Stores in PostgreSQL
         │            Pushes coordinates to Redis
         │
         ▼
    ┌─────────┐
    │  Redis  │ ◄──────────────────┐
    │ Queues  │                    │
    └────┬────┘              Returns alerts
         │                  (Optional downstream)
         │ Coordinates
         │
         ▼
    ┌────────────────────┐
    │ Alert Processor    │  Analyzes locations
    │ Microservice       │  Detects geofence events
    │ (Scalable)         │  Generates alerts
    └────────────────────┘
```

## Quick Start Guide

### 1. Start All Services
```bash
# Make script executable
chmod +x scripts/microservices.sh

# Start everything
./scripts/microservices.sh start

# Check status
./scripts/microservices.sh status
```

### 2. View Logs
```bash
# View all logs
./scripts/microservices.sh logs

# View specific service
./scripts/microservices.sh logs alert-processor
./scripts/microservices.sh logs api
```

### 3. Check Queue Statistics
```bash
./scripts/microservices.sh queue-stats
```

### 4. Monitor Health
```bash
./scripts/microservices.sh health
```

## What's New in the Code

### API Changes (app/main.py)
```python
# Now initializes Redis message queue
message_queue = MessageQueue(os.getenv('REDIS_URL'))
collection_manager.message_queue = message_queue
```

### Data Collection Changes (app/scraper_async.py)
```python
# Pushes coordinates to Redis for async processing
self.message_queue.push_coordinate(
    ruta=normalized_data['ruta'],
    latitude=normalized_data['ns_latitude'],
    longitude=normalized_data['ew_longitude'],
    ...
)
```

### Shared Package Usage
```python
# All services import from shared package
from shared.message_queue import MessageQueue
from shared.location_alerts import LocationAnalyzer
```

## Environment Configuration

Update your `.env` file with:
```bash
# Existing variables (keep as-is)
POSTGRES_USER=...
POSTGRES_PASSWORD=...
POSTGRES_DB=...
DATABASE_URL=postgresql://...
SCRAPER_EMAIL=...
SCRAPER_PASSWORD=...

# New variables
REDIS_URL=redis://redis:6379/0
```

## Service Dependencies

```
PostgreSQL ──┐
             ├──► FastAPI API ──► Redis ──► Alert Processor
             │
PGAdmin ─────┘
```

- **PostgreSQL**: Required (stores collected data)
- **Redis**: Required (message queue)
- **API**: Required (data collection)
- **Alert Processor**: Automatically started (processes alerts)
- **PGAdmin**: Optional (database admin)

## Important Notes

### Old Files Removed (Now Using Shared Package)
The following files have been removed from `app/` in favor of the shared package:
- ~~`app/message_queue.py`~~ → **Removed** (use `shared.message_queue`)
- ~~`app/location_alerts.py`~~ → **Removed** (use `shared.location_alerts`)
- ~~`app/alert_consumer.py`~~ → **Removed** (use `microservices/alert-processor`)

All services now import from the `shared-package` for consistency.

### Backwards Compatibility
The system is fully backwards compatible:
- Existing API endpoints work unchanged
- Database schema is unchanged
- All existing data is preserved

## Development Tools & Monitoring

### Real-Time Queue Monitoring
```bash
# Visual monitor with auto-refresh
python redis_monitor.py --interval 1

# Shows:
# - Queue lengths
# - Memory usage
# - Preview of coordinates and alerts
# - Color-coded severity levels
```

### Testing Alert Processor
```bash
# Test geofence entry
python test_alert_processor.py --scenario zone

# Test batch processing
python test_alert_processor.py --scenario batch

# Load test
python test_alert_processor.py --load 100
```

### Hot Reload Development
```bash
# Start with development overrides (code mounted as volumes)
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Make code changes
vim microservices/alert-processor/main.py

# Just restart (no rebuild needed!)
docker restart alert_processor
```

### Redis Queue Inspection
```bash
# Connect to Redis CLI
docker exec -it redis_queue redis-cli

# Check queue lengths
LLEN coordinate_queue
LLEN alert_queue

# Peek at queue contents
LRANGE coordinate_queue 0 9

# Monitor all Redis commands in real-time
MONITOR
```

### Alert Processor Management
```bash
# Restart independently (FastAPI keeps running)
docker restart alert_processor

# Stop for development
docker stop alert_processor

# Rebuild after code changes
docker-compose build alert-processor && docker-compose up -d alert_processor

# View logs
docker logs -f alert_processor

# Scale up consumers
docker-compose up -d --scale alert-processor=3
```

## Next Steps

### Immediate Actions
1. Update Docker images: `docker-compose build`
2. Start services: `./scripts/microservices.sh start`
3. Verify health: `./scripts/microservices.sh health`

### Future Enhancements
1. **Alert Handlers**: Add webhook/email/SMS notifications
2. **Database Zones**: Move geofence zones to PostgreSQL
3. **Metrics**: Add Prometheus monitoring
4. **Real-time Dashboard**: WebSocket alerts
5. **Kubernetes**: Deploy on K8s for auto-scaling

## Troubleshooting

### Alert Processor Not Processing
```bash
# Check logs
./scripts/microservices.sh logs alert-processor

# Check queue
./scripts/microservices.sh queue-stats

# Verify Redis connection
docker exec alert_processor redis-cli -h redis ping
```

### API Not Pushing to Queue
```bash
# Check API logs
./scripts/microservices.sh logs api

# Verify Redis is running
./scripts/microservices.sh health
```

### Database Connection Issues
```bash
# Check database logs
docker-compose logs db

# Verify database is accessible
docker exec db psql -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT 1"
```

## Documentation References

### Core Documentation
- **[MICROSERVICES_GUIDE.md](microservices.md)** - Complete architecture and technical details
- **[DEPLOYMENT_GUIDE.md](../guides/deployment.md)** - Production deployment instructions

### Redis Queue System
- **[REDIS_QUEUE_GUIDE.md](../guides/redis/queue-guide.md)** - How Redis queues work, where data is stored, monitoring
- **[REDIS_QUICK_REFERENCE.md](../guides/redis/quick-reference.md)** - Quick command reference and common scenarios

### Alert Processor Development
- **[ALERT_PROCESSOR_GUIDE.md](../guides/alert-processor.md)** - How the consumer works, restart procedures
- **[DEV_WORKFLOW.md](../guides/development/workflow.md)** - Development workflows, hot reload, testing strategies
- **[ARCHITECTURE_OVERVIEW.md](overview.md)** - Complete visual architecture guide

### Development Tools
- **[redis_monitor.py](./redis_monitor.py)** - Real-time queue monitoring tool
- **[test_alert_processor.py](./test_alert_processor.py)** - Testing tool for alert processor
- **[docker-compose.dev.yml](./docker-compose.dev.yml)** - Development overrides for hot reload

## Support for Microservices Features

### Message Queue Features
- ✅ Push coordinates to queue
- ✅ Pop coordinates for processing
- ✅ Push alerts to queue
- ✅ Health checks
- ✅ Queue length monitoring

### Location Analysis Features
- ✅ Geofence zones
- ✅ Zone entry/exit detection
- ✅ Multi-zone tracking
- ✅ Route status tracking
- ✅ Alert generation

### Scaling Features
- ✅ Multiple alert processors
- ✅ Independent service restart
- ✅ Network isolation
- ✅ Health monitoring

### Future Features (Ready for Implementation)
- 🔄 Database-driven zone configuration
- 🔄 Multiple alert backend handlers
- 🔄 Kubernetes deployment
- 🔄 Prometheus metrics integration
- 🔄 Distributed tracing
- 🔄 Alert webhooks/notifications

## Questions or Issues?

Refer to:
1. [MICROSERVICES_GUIDE.md](microservices.md) for architecture details
2. [DEPLOYMENT_GUIDE.md](../guides/deployment.md) for deployment help
3. Service logs: `./scripts/microservices.sh logs [service-name]`
4. Health check: `./scripts/microservices.sh health`

---

**Version**: 1.0  
**Last Updated**: February 2026  
**Architecture**: Microservices + Message Queue
