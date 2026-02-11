# VTrack Microservices Architecture

## Overview

The VTrack system has been restructured to follow a microservices architecture, making it easier to scale, deploy, and maintain individual components independently.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        MESSAGE QUEUE (Redis)                    │
│                   - Coordinate Queue                            │
│                   - Alert Queue                                 │
└─────────────────────────────────────────────────────────────────┘
         ▲                                              ▲
         │                                              │
         │ PUSH DATA                              CONSUME ALERTS
         │                                              │
    ┌────┴────┐                                  ┌─────┴─────┐
    │          │                                  │           │
┌───┴──┐  ┌────▼────┐                      ┌────▼────┐      
│ FastAPI │  │PostgreSQL    │                      │ Alert     │      
│   API    │  │ Database}     │                      │Processor  │      
│          │  │              │                      │Service    │      
└─────────┘  └──────────────┘                      └──────────┘
     │
     │ Collects coordinates
     │ from remote API
     │
     └──> Saves to DB
          Pushes to Redis
```

## Services

### 1. FastAPI API (`app/`)
The main application service that:
- Handles HTTP requests and API endpoints
- Collects coordinate data from remote sources
- Stores data in PostgreSQL
- Pushes coordinates to Redis queue for analysis
- Manages scheduling and collection lifecycle

**Port:** 8000  
**Debug Port:** 5678

### 2. Alert Processor Microservice (`microservices/alert-processor/`)
A standalone service that:
- Consumes coordinates from Redis queue
- Performs geofencing analysis on locations
- Detects when buses/routes enter/exit predefined zones
- Generates alerts when geofence conditions are met
- Pushes alerts to the alert queue for downstream processing

**Runs independently** - can be deployed on separate infrastructure

### 3. Data Collector Microservice (`microservices/data-collector/`)
Optional standalone service for:
- Independent data collection (alternative to API-based collection)
- Scheduled collection tasks
- Currently a placeholder for future distributed collection scenarios

**Status:** Optional (disabled by default in docker-compose.yml)

### 4. Shared Package (`shared-package/`)
Python package containing shared code used by all services:
- `MessageQueue`: Redis communication abstraction
- `LocationAnalyzer`: Geofencing logic
- `LocationAlert`: Alert data structures
- `Zone`: Geofence zone definitions

Installed as a Python package in all service containers.

## File Structure

```
vtrack/
├── app/                          # Main FastAPI application
│   ├── main.py                   # App entry point
│   ├── scraper_async.py         # Data collection logic
│   ├── models.py                # SQLAlchemy & Pydantic models
│   ├── database.py              # DB configuration
│   ├── data_server.py           # Data API routes
│   ├── message_queue.py         # DEPRECATED (use shared package)
│   ├── location_alerts.py       # DEPRECATED (use shared package)
│   └── alert_consumer.py        # DEPRECATED (use microservice)
│
├── microservices/
│   ├── alert-processor/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── main.py
│   └── data-collector/
│       ├── Dockerfile
│       ├── requirements.txt
│       └── main.py
│
├── shared-package/               # Shared Python package
│   ├── setup.py
│   ├── pyproject.toml
│   └── src/shared/
│       ├── __init__.py
│       ├── message_queue.py
│       └── location_alerts.py
│
├── docker-compose.yml            # Orchestration config
├── Dockerfile                    # Main API Dockerfile
├── requirements.txt              # API dependencies
│
└── scripts/                      # Helper scripts
    └── (future enhancement scripts)
```

## Starting the System

### Development Mode (with Docker Compose)

```bash
# Build and start all services
docker-compose up

# In another terminal, view logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f alert-processor
docker-compose logs -f api

# Special reset trick
docker-compose down --volumes --remove-orphans && docker-compose up -d --build
```

### Production Considerations

1. **Database Migrations**: Run automatically via `migrate` service
2. **Redis Persistence**: Configure `redis.conf` for data persistence
3. **Multiple Alert Processors**: Scale by running multiple alert-processor containers
4. **Monitoring**: Add health checks and metrics collection
5. **Logging**: Centralize logs using ELK stack or similar

## Message Queue Communication

### How Redis Queues Work

VTrack uses **Redis Lists** as queues with FIFO (First In, First Out) pattern:

```
Producer (FastAPI)                Redis                Consumer (alert-processor)
       │                           │                            │
       │  LPUSH (add to front)     │                            │
       ├──────────────────────────►│                            │
       │                           │                            │
       │                      ┌────▼────┐                       │
       │                      │ [newest]│                       │
       │                      │    ↓    │                       │
       │                      │ [item 3]│                       │
       │                      │ [item 2]│                       │
       │                      │ [item 1]│                       │
       │                      │ [oldest]│                       │
       │                      └────┬────┘                       │
       │                           │  RPOP (remove from end)    │
       │                           ├───────────────────────────►│
       │                           │                            │
```

**Storage Location:**
- **In-Memory:** All queues stored in RAM for ultra-fast access
- **Container:** `redis_queue` (redis:7-alpine image)
- **Port:** 6379 (accessible at `localhost:6379` from host)
- **Database:** 0 (Redis has 16 databases, we use DB 0)
- **Persistence:** Optional disk snapshots to `/data` volume

**Queue Operations:**
- `LPUSH coordinate_queue <json>` - Add to front of queue
- `RPOP coordinate_queue` - Remove from end of queue (oldest first)
- `LLEN coordinate_queue` - Get queue length
- `LRANGE coordinate_queue 0 -1` - View all items (without removing)

### Coordinate Queue

**Producer:** FastAPI API (scraper_async.py)
**Consumer:** Alert Processor Microservice
**Key:** `coordinate_queue`

**Message Format:**
```json
{
  "ruta": 101,
  "latitude": 4.7110,
  "longitude": -74.0059,
  "position_ts": "2024-02-09T10:30:45-05:00",
  "route_status": "En recorrido",
  "student_status": "Subio",
  "queued_at": "2024-02-09T10:30:46-05:00"
}
```

**Flow:**
1. scraper_async.py collects coordinate from remote API
2. Saves to PostgreSQL database
3. Calls `message_queue.push_coordinate(...)` → `LPUSH coordinate_queue <json>`
4. alert-processor polls: `message_queue.pop_coordinate()` → `RPOP coordinate_queue`
5. Analyzes and generates alerts

### Alert Queue

**Producer:** Alert Processor Microservice
**Consumer:** Downstream systems (webhooks, notifications, dashboards - future)
**Key:** `alert_queue`

**Message Format:**
```json
{
  "ruta": 101,
  "latitude": 4.7110,
  "longitude": -74.0059,
  "alert_type": "GEOFENCE_ENTRY",
  "area_name": "School Zone",
  "severity": "INFO",
  "timestamp": "2024-02-09T10:30:46-05:00"
}
```

**Flow:**
1. alert-processor detects geofence entry/exit
2. Creates LocationAlert object
3. Calls `message_queue.push_alert(...)` → `LPUSH alert_queue <json>`
4. Downstream consumers can poll: `RPOP alert_queue` (future implementation)

### Monitoring Queues

**Real-time Monitor:**
```bash
python redis_monitor.py --interval 1
```

**Command Line:**
```bash
# Check sizes
docker exec redis_queue redis-cli LLEN coordinate_queue
docker exec redis_queue redis-cli LLEN alert_queue

# Watch size change
watch -n 1 'docker exec redis_queue redis-cli LLEN coordinate_queue'

# View contents
docker exec redis_queue redis-cli LRANGE coordinate_queue 0 9
```

**See Also:** [REDIS_QUEUE_GUIDE.md](../guides/redis/queue-guide.md) for complete queue documentation

## Scaling Strategies

### Horizontal Scaling
- **Alert Processor**: Run multiple instances consuming from the same queue
- **API**: Run multiple instances behind a load balancer
- **Database**: Implement read replicas for reporting queries

### Vertical Scaling
- Increase container resource limits
- Optimize geofence algorithms
- Implement caching in Redis

## Configuration

### Environment Variables

Required:
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
- `DATABASE_URL`
- `REDIS_URL`
- `SCRAPER_EMAIL`, `SCRAPER_PASSWORD`

Optional:
- `PGADMIN_EMAIL`, `PGADMIN_PASSWORD`
- Custom zone definitions (future enhancement)

### Zone Configuration

Currently hardcoded in `shared-package/src/shared/location_alerts.py`:
```python
Zone(
    zone_id=1,
    name="School Zone",
    latitude=4.7110,
    longitude=-74.0059,
    radius_meters=500,
    alert_type=AlertType.GEOFENCE_ENTRY,
    severity=AlertSeverity.INFO
)
```

Future enhancement: Load zones from database or config file.

## How Alert Processor Works

### Startup and Execution

The alert-processor is a **Python script running in a Docker container**, kept alive by Docker's restart policy:

```
docker-compose up
      ↓
Reads docker-compose.yml (line 117: alert-processor service)
      ↓
Builds from microservices/alert-processor/Dockerfile
      ↓
Dockerfile executes: CMD ["python", "main.py"]
      ↓
main.py runs: AlertConsumer().start(poll_interval=1)
      ↓
Infinite consumer loop starts:
   while True:
       coordinate = redis.rpop('coordinate_queue')
       if coordinate:
           alerts = analyze_coordinate(...)
           if alerts:
               redis.lpush('alert_queue', ...)
       sleep(1 second)
```

**It's NOT a daemon in the traditional sense:**
- No systemd/supervisor needed
- Docker daemon manages the process
- `restart: always` keeps it alive if it crashes
- Runs in foreground inside container

### Consumer Loop Explained

```python
def start(self, poll_interval: int = 1):
    """Start the consumer service."""
    while self.is_running:
        # 1. Pop coordinate from Redis (FIFO from end of list)
        coordinate = self.message_queue.pop_coordinate()

        if coordinate:
            # 2. Extract data
            ruta = coordinate.get('ruta')
            latitude = coordinate.get('latitude')
            longitude = coordinate.get('longitude')

            # 3. Analyze with geofencing logic
            alerts = self.location_analyzer.analyze_coordinate(
                ruta=ruta,
                latitude=latitude,
                longitude=longitude
            )

            # 4. Push any generated alerts
            for alert in alerts:
                self.message_queue.push_alert(...)

        # 5. Wait before next poll
        time.sleep(poll_interval)
```

### Independence from FastAPI

The alert-processor is **completely independent**:
- Separate Docker container
- Separate process
- Only communicates via Redis queues
- Can be restarted without affecting FastAPI
- FastAPI can be restarted without affecting alert-processor

**Benefits:**
- **No data loss:** Coordinates stay in Redis during restarts
- **Easy testing:** Stop consumer, test changes, restart
- **Scalability:** Run multiple consumers for higher throughput
- **Resilience:** One service crashing doesn't affect the other

### Development Workflow

**Standard Mode (Rebuild Required):**
```bash
# 1. Edit code
vim microservices/alert-processor/main.py

# 2. Rebuild image
docker-compose build alert-processor

# 3. Restart container
docker-compose up -d alert-processor

# 4. Watch logs
docker logs -f alert_processor
```

**Fast Mode (Hot Reload):**
```bash
# 1. Start with dev overrides (mounts code as volume)
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# 2. Edit code
vim microservices/alert-processor/main.py

# 3. Just restart (no rebuild!)
docker restart alert_processor

# 4. Watch logs
docker logs -f alert_processor
```

**Testing Changes:**
```bash
# Push test coordinate
python test_alert_processor.py --scenario zone

# Or manually
docker exec redis_queue redis-cli LPUSH coordinate_queue '{
  "ruta": 101,
  "latitude": 4.7110,
  "longitude": -74.0059
}'

# Watch it get processed
docker logs -f alert_processor
```

**See Also:**
- [ALERT_PROCESSOR_GUIDE.md](../guides/alert-processor.md) for complete consumer documentation
- [DEV_WORKFLOW.md](../guides/development/workflow.md) for development workflows

## Monitoring & Debugging

### Health Checks
All services have health checks configured:
- PostgreSQL: `pg_isready` command
- Redis: `redis-cli ping`
- API: HTTP `/collect/status` endpoint
- Alert Processor: Logs output and queue statistics

### Debugging
Enable debug logging via environment variables:
```yaml
environment:
  LOG_LEVEL: DEBUG
```

### Queue Inspection

**Option 1: Use Python Monitor (Recommended)**
```bash
python redis_monitor.py --interval 1
```
Shows real-time visual display of queues, coordinates, and alerts.

**Option 2: Redis CLI**
```bash
# Connect to Redis
docker exec -it redis_queue redis-cli

# Check queue lengths
LLEN coordinate_queue
LLEN alert_queue

# View queue contents (without removing)
LRANGE coordinate_queue 0 9    # First 10 items
LRANGE coordinate_queue -10 -1  # Last 10 items

# Monitor all Redis activity in real-time
MONITOR

# Check memory usage
INFO memory
```

**Option 3: Test Script**
```bash
python test_alert_processor.py --scenario status
```

**See Also:** [REDIS_QUEUE_GUIDE.md](../guides/redis/queue-guide.md) for complete Redis queue documentation.

## Future Enhancements

1. **Database-driven Zones**: Move zone configuration to PostgreSQL
2. **Alert Handlers**: Multiple backends for alert notifications (email, SMS, webhooks)
3. **Metrics**: Prometheus metrics for monitoring
4. **API Gateway**: Add Kong or Nginx for API management
5. **Distributed Tracing**: Implement OpenTelemetry
6. **Async Task Processing**: Move to Celery for long-running tasks
7. **Real-time Analytics**: Add analytics microservice
8. **Machine Learning**: Anomaly detection service for route behavior

## Troubleshooting

### Alert Processor not processing

**Check Status:**
```bash
# Check if running
docker ps | grep alert_processor

# Check queue status
python test_alert_processor.py --scenario status

# Check logs for errors
docker logs alert_processor --tail 50 | grep -i error
```

**Common Fixes:**
```bash
# Restart consumer
docker restart alert_processor

# Rebuild and restart
docker-compose build alert-processor
docker-compose up -d alert_processor

# Check Redis connection
docker logs alert_processor | grep "Redis connection"
```

### Queue Growing (Coordinates Not Being Consumed)

**Diagnose:**
```bash
# Monitor queue size
watch -n 1 'docker exec redis_queue redis-cli LLEN coordinate_queue'

# Check consumer processing rate
docker logs alert_processor | grep "Processed"
```

**Fix:**
- Consumer crashed? Check: `docker ps | grep alert_processor`
- Too slow? Scale up: `docker-compose up -d --scale alert-processor=3`
- Stuck? Restart: `docker restart alert_processor`

### API not pushing to queue

**Check:**
```bash
# Verify Redis is running
docker ps | grep redis

# Check API logs for push operations
docker logs fastapi_api | grep "Pushed coordinate"

# Test Redis connectivity from API
docker exec fastapi_api python -c "
import redis
r = redis.from_url('redis://redis:6379/0')
print('Connected:', r.ping())
"
```

### No Alerts Being Generated

**Test:**
```bash
# Push a test coordinate in a known geofence zone
python test_alert_processor.py --scenario zone

# Check alert queue
docker exec redis_queue redis-cli LRANGE alert_queue 0 -1

# Check consumer logs for alert generation
docker logs alert_processor | grep "ALERT"
```

### Code Changes Not Taking Effect

**Solution:**
```bash
# Force rebuild without cache
docker-compose build --no-cache alert-processor
docker-compose up -d alert_processor

# Or use dev mode with hot reload
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
docker restart alert_processor
```

### Database connection errors
1. Verify PostgreSQL is healthy: `docker-compose ps`
2. Check DATABASE_URL format
3. Review Docker network connectivity

## Additional Documentation

### VTrack Project Documentation
- **[MICROSERVICES_README.md](quick-reference.md)** - Quick start and overview
- **[ARCHITECTURE_OVERVIEW.md](overview.md)** - Complete visual architecture
- **[REDIS_QUEUE_GUIDE.md](../guides/redis/queue-guide.md)** - Redis queue internals and monitoring
- **[REDIS_QUICK_REFERENCE.md](../guides/redis/quick-reference.md)** - Redis command cheat sheet
- **[ALERT_PROCESSOR_GUIDE.md](../guides/alert-processor.md)** - Alert processor deep dive
- **[DEV_WORKFLOW.md](../guides/development/workflow.md)** - Development workflows and best practices
- **[DEPLOYMENT_GUIDE.md](../guides/deployment.md)** - Production deployment

### Development Tools
- **[redis_monitor.py](./redis_monitor.py)** - Real-time queue monitoring
- **[test_alert_processor.py](./test_alert_processor.py)** - Testing tool for alert processor
- **[docker-compose.dev.yml](./docker-compose.dev.yml)** - Hot reload configuration

### External References
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Redis Documentation](https://redis.io/documentation)
- [Redis Lists](https://redis.io/docs/data-types/lists/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Geopy Documentation](https://geopy.readthedocs.io/)
