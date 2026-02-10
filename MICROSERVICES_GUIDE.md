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

### Coordinate Queue
Data pushed by: FastAPI API (during data collection)  
Consumed by: Alert Processor Microservice

Message format:
```json
{
  "ruta": 101,
  "latitude": 4.7110,
  "longitude": -74.0059,
  "position_ts": "2024-02-09T10:30:45",
  "route_status": "En recorrido",
  "student_status": "Subio",
  "queued_at": "2024-02-09T10:30:46"
}
```

### Alert Queue
Data pushed by: Alert Processor Microservice  
Consumed by: Downstream systems (webhooks, notifications, dashboards)

Message format:
```json
{
  "ruta": 101,
  "latitude": 4.7110,
  "longitude": -74.0059,
  "alert_type": "GEOFENCE_ENTRY",
  "area_name": "School Zone",
  "severity": "INFO",
  "timestamp": "2024-02-09T10:30:46"
}
```

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
```bash
# Connect to Redis
docker exec -it redis_queue redis-cli

# Check queue lengths
LLEN coordinate_queue
LLEN alert_queue
```

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
1. Check Redis connection: `docker logs alert_processor`
2. Verify coordinate queue has data: `redis-cli LLEN coordinate_queue`
3. Check consumer logs for errors

### API not pushing to queue
1. Verify Redis is running: `docker ps | grep redis`
2. Check REDIS_URL environment variable
3. Review API logs: `docker logs fastapi_api`

### Database connection errors
1. Verify PostgreSQL is healthy: `docker-compose ps`
2. Check DATABASE_URL format
3. Review Docker network connectivity

## References

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Redis Documentation](https://redis.io/documentation)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
