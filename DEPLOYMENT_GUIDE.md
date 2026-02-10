# Microservices Deployment Guide

## Overview

This guide provides instructions for deploying VTrack microservices in different environments.

## Local Development Setup

### Prerequisites
- Docker and Docker Compose installed
- Python 3.10+ (for local development)
- git for version control

### Quick Start
```bash
# Clone the repository
git clone <repo-url>
cd vtrack

# Make the microservices script executable
chmod +x scripts/microservices.sh

# Start all services
./scripts/microservices.sh start

# Check service status
./scripts/microservices.sh status

# View logs
./scripts/microservices.sh logs api

#tail the api container logs in real time
docker-compose logs -f api
```

### CI / Dev note

If you modify code inside `shared-package`, rebuild images or install the package into running containers so the change is available inside service environments. Recommended development workflows:

- Rebuild and restart the API service:

```bash
docker-compose build api
docker-compose up -d api
```

- Or install editable package into a running container for quick iteration:

```bash
docker-compose exec api pip install -e /app/shared-package
```

In CI pipelines prefer rebuilding images (run `docker-compose build`) so the final images contain the packaged dependencies.

## Docker Compose Deployment

### Production Environment Variables

Create `.env.production`:
```bash
# Database Configuration
POSTGRES_USER=vtrack_prod
POSTGRES_PASSWORD=<strong-password>
POSTGRES_DB=vtrack_production
DATABASE_URL=postgresql://vtrack_prod:<password>@db:5432/vtrack_production

# Redis Configuration
REDIS_URL=redis://redis:6379/0

# Scraper Credentials
LOGIN_EMAIL=<scraper-email>
LOGIN_PASSWORD=<scraper-password>

# PGAdmin Configuration
PGADMIN_EMAIL=admin@vtrack.local
PGADMIN_PASSWORD=<pgadmin-password>
```

### Deployment Commands

```bash
# Load production environment
export $(cat .env.production | xargs)

# Build production images
docker-compose build

# Start services in detached mode
docker-compose -f docker-compose.yml up -d

# View running services
docker-compose ps

# Check service health
./scripts/microservices.sh health

# View logs
docker-compose logs -f alert-processor
```

## Scaling Strategies

### Alert Processor Horizontal Scaling

For multi-instance deployment (requires Docker Swarm or Kubernetes):

```bash
# Docker Swarm
docker service create --name alert-processor --replicas 3 <image>

# Kubernetes
kubectl scale deployment alert-processor --replicas=3
```

Or using docker-compose with manual replication:
```bash
# Start 3 alert processor instances
docker-compose up -d --scale alert-processor=3
```

### Database Replication

For production, implement PostgreSQL replication:
1. Set up primary-replica configuration
2. Configure read replicas for reporting queries
3. Implement automatic failover

### Redis Clustering

For high availability:
```bash
# Redis Sentinel configuration
redis-server --sentinel sentinel.conf --port 26379
```

## Monitoring & Logging

### Health Checks

The docker-compose configuration includes health checks for:
- PostgreSQL (5 second interval)
- Redis (5 second interval)
- API (via HTTP status)

View health status:
```bash
docker-compose ps  # Look for the STATUS column
```

### Logging

Configure centralized logging:

#### Option 1: ELK Stack
```yaml
logging:
  driver: json-file
  options:
    max-size: "10m"
    max-file: "3"
    labels: "service_name"
```

#### Option 2: Splunk
```yaml
environment:
  SPLUNK_HEC_TOKEN: <token>
  SPLUNK_HEC_ENDPOINT: https://splunk.example.com:8088
logging:
  driver: splunk
  options:
    splunk-token: $SPLUNK_HEC_TOKEN
    splunk-url: $SPLUNK_HEC_ENDPOINT
```

#### Option 3: Datadog
```yaml
environment:
  DD_API_KEY: <api-key>
  DD_SITE: datadoghq.com
logging:
  driver: datadog
  options:
    dd-service: "vtrack-microservices"
    dd-source: "docker"
```

## Backup and Recovery

### Database Backup

```bash
# Full backup
docker exec postgres_db pg_dump -U $POSTGRES_USER $POSTGRES_DB > backup.sql

# Restore from backup
docker exec -i postgres_db psql -U $POSTGRES_USER $POSTGRES_DB < backup.sql

# Automated daily backup
0 2 * * * docker exec postgres_db pg_dump -U $POSTGRES_USER $POSTGRES_DB > /backups/vtrack_$(date +\%Y\%m\%d).sql
```

### Redis Backup

```bash
# Create a snapshot
docker exec redis_queue redis-cli BGSAVE

# Copy the dump file
docker cp redis_queue:/data/dump.rdb ./redis_backup.rdb
```

## Security Considerations

### Network Security

1. Use internal Docker networks (configured in docker-compose.yml)
2. Expose only necessary ports:
   - API: 8000 (external)
   - PGAdmin: 8080 (internal/VPN only)
   - Redis: Not exposed (internal only)
   - PostgreSQL: Not exposed (internal only)

### Secret Management

Avoid storing secrets in `.env` files for production. Use:
- Docker Secrets (Swarm mode)
- Kubernetes Secrets
- HashiCorp Vault
- AWS Secrets Manager

### Database Security

```bash
# Strong password policy
export POSTGRES_PASSWORD=$(openssl rand -base64 32)

# SSL connections
DATABASE_URL=postgresql+psycopg://user:pwd@db/db?sslmode=require
```

## Performance Tuning

### Redis Configuration

```conf
# redis.conf optimizations
maxmemory 2gb
maxmemory-policy allkeys-lru
tcp-backlog 511
timeout 0
```

### PostgreSQL Tuning

```sql
-- Adjust based on your hardware
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET work_mem = '16MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;

-- Restart required
SELECT pg_reload_conf();
```

### Alert Processor Optimization

```python
# Adjust poll interval based on expected volume
consumer.start(poll_interval=0.5)  # Faster processing
consumer.start(poll_interval=2)    # Lower CPU usage
```

## Troubleshooting

### Service Won't Start

```bash
# Check logs
docker-compose logs <service-name>

# Check Docker daemon
docker ps -a

# Verify network connectivity
docker network ls
```

### High Memory Usage

```bash
# Check memory stats
docker stats

# Limit service memory
# In docker-compose.yml:
services:
  alert-processor:
    deploy:
      resources:
        limits:
          memory: 512M
```

### Connection Refused

```bash
# Test service connectivity
docker exec <container> curl http://<service>:8000/health

# Check network interfaces
docker exec <container> ip -4 addr show
```

## Upgrading Services

### Rolling Update Strategy

```bash
# 1. Build new image
docker-compose build api

# 2. Bring down API only
docker-compose stop api

# 3. Start new version
docker-compose up -d api

# 4. Verify health
./scripts/microservices.sh health
```

## Disaster Recovery Plan

### RTO/RPO Targets
- **RTO (Recovery Time Objective):** 1 hour
- **RPO (Recovery Point Objective):** 15 minutes

### Recovery Procedures

1. **Database Failure:** Restore from latest backup
2. **Redis Failure:** Rebuild from source (non-critical)
3. **Service Failure:** Auto-restart via `restart: always`
4. **Complete System Failure:** 
   - Restore database backup
   - Pull latest images
   - Run `docker-compose up -d`

## Monitoring Dashboard

### Recommended Tools

1. **Prometheus + Grafana**
   ```yaml
   services:
     prometheus:
       image: prom/prometheus
       ports:
         - "9090:9090"
   ```

2. **Portainer** (Docker management)
   ```yaml
   services:
     portainer:
       image: portainer/portainer-ce
       ports:
         - "9000:9000"
   ```

3. **OpenTelemetry** (Distributed tracing)
   - Add OpenTelemetry instrumentation
   - Export to Jaeger or Zipkin

### Key Metrics to Monitor

- Coordinate queue length
- Alert queue length
- Alert processor processing rate
- Database connection pool usage
- Redis memory usage
- API response times
- Error rates

## Cost Optimization

### Resource Limits

```yaml
services:
  alert-processor:
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 256M
        reservations:
          cpus: '0.25'
          memory: 128M
```

### Auto-scaling

For production, consider:
- Horizontal Pod Autoscaler (Kubernetes)
- Target Tracking Scaling (AWS)
- Custom scaling logic based on queue depth

## Maintenance Windows

### Planned Downtime Schedule

- Update database: Sunday 2-3 AM
- Service updates: Sunday 3-4 AM
- Capacity planning: Monthly review

### Zero-Downtime Deployment

1. Deploy new version alongside old
2. Route new traffic to new version
3. Gradually shift traffic
4. Remove old version

## References

- [Docker Compose Production Setup](https://docs.docker.com/compose/production/)
- [PostgreSQL High Availability](https://www.postgresql.org/docs/current/different-replication-solutions.html)
- [Redis Persistence](https://redis.io/topics/persistence)
- [Kubernetes Migration](https://kubernetes.io/)
