# Troubleshooting Guide

Common issues and solutions for VTrack Docker containers and services.

---

## 🚨 Quick Fixes

### Services Won't Start - ContainerConfig Error

**Symptom:**
```bash
$ docker-compose up -d
ERROR: for db  'ContainerConfig'
ERROR: for redis  'ContainerConfig'
KeyError: 'ContainerConfig'
```

**Cause:** Orphaned or corrupted containers from a previous run. This happens when:
- Containers were stopped improperly (system crash, Docker daemon restart)
- Docker metadata got corrupted
- Mixing different docker-compose commands without proper cleanup

**Solution 1: Clean Restart (Data Preserved)**
```bash
# Stop and remove all containers/networks
docker-compose down

# Remove any orphaned containers by ID
docker ps -a | grep -E "postgres_db|redis_queue|alert_processor"
# If you see containers with IDs like "038f733ebf48_postgres_db", remove them:
docker rm -f <container_id>

# Start fresh
docker-compose up -d
```

**Solution 2: Full Clean Slate (⚠️ DATA LOSS)**

> **⚠️ WARNING: This will delete ALL data including your database!**
> 
> **Before proceeding:**
> ```bash
> # Backup your database first!
> docker-compose exec db pg_dump -U ${POSTGRES_USER} -d ${POSTGRES_DB} > backup_$(date +%Y%m%d_%H%M%S).sql
> ```

```bash
# Remove everything including volumes
docker-compose down -v

# Verify volumes are gone
docker volume ls | grep vtrack

# Start fresh (will rebuild database from scratch)
docker-compose up -d --build
```

---

## 🔄 Clean Slate Workflows

### When Do You Need a Clean Slate?

Choose based on your situation:

| Situation | Command | Data Loss? | Use Case |
|-----------|---------|------------|----------|
| Service not responding | `docker-compose restart <service>` | ❌ No | Quick fix, keeps data |
| Config change | `docker-compose up -d` | ❌ No | Apply docker-compose.yml changes |
| Code change | `docker-compose up -d --build` | ❌ No | Rebuild images, keep data |
| Container corrupted | `docker-compose down && docker-compose up -d` | ❌ No | Remove containers, keep data |
| **Full reset** | `docker-compose down -v` | ⚠️ **YES** | Delete everything including DB |

### Level 1: Soft Restart (No Data Loss)

For minor issues (service not responding):

```bash
# Restart specific service
docker-compose restart api

# Or restart all services
docker-compose restart
```

**What happens:** Container stops and starts, all data preserved.

### Level 2: Rebuild (No Data Loss)

For code changes or dependency updates:

```bash
# Rebuild and restart specific service
docker-compose up -d --build api

# Or rebuild everything
docker-compose up -d --build
```

**What happens:** Rebuilds Docker images, recreates containers, volumes (data) preserved.

### Level 3: Clean Containers (No Data Loss)

For container corruption or network issues:

```bash
# Stop and remove containers/networks
docker-compose down

# Recreate everything
docker-compose up -d
```

**What happens:** Removes containers and networks, volumes (data) preserved.

### Level 4: Nuclear Option (⚠️ DATA LOSS)

For complete reset or testing fresh install:

> **⚠️ DANGER ZONE: This deletes ALL data!**

```bash
# 1. BACKUP FIRST!
docker-compose exec db pg_dump -U ${POSTGRES_USER} -d ${POSTGRES_DB} > backup.sql

# 2. Stop and remove EVERYTHING
docker-compose down -v

# 3. Optional: Remove old images to force full rebuild
docker images | grep vtrack
docker rmi $(docker images | grep vtrack | awk '{print $3}')

# 4. Start fresh
docker-compose up -d --build

# 5. Restore data if needed
cat backup.sql | docker-compose exec -T db psql -U ${POSTGRES_USER} -d ${POSTGRES_DB}
```

**What happens:** Everything deleted - containers, networks, volumes, all data gone.

---

## 🗄️ Database Backup & Restore

### Quick Backup

```bash
# Backup to file
docker-compose exec db pg_dump -U ${POSTGRES_USER} -d ${POSTGRES_DB} > backup_$(date +%Y%m%d_%H%M%S).sql

# Verify backup
ls -lh backup_*.sql
```

### Quick Restore

```bash
# Restore from file
cat backup_20260215_120000.sql | docker-compose exec -T db psql -U ${POSTGRES_USER} -d ${POSTGRES_DB}

# Or using docker exec
docker-compose exec -T db psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} < backup_20260215_120000.sql
```

### Backup Before Dangerous Operations

Always backup before:
- Running `docker-compose down -v`
- Running database migrations
- Upgrading PostgreSQL version
- Testing destructive operations
- Making schema changes

**Automated backup script:**
```bash
#!/bin/bash
# Save as: scripts/backup_db.sh

BACKUP_DIR="./backups"
mkdir -p $BACKUP_DIR

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/vtrack_backup_$TIMESTAMP.sql"

echo "Creating backup: $BACKUP_FILE"
docker-compose exec -T db pg_dump -U ${POSTGRES_USER} -d ${POSTGRES_DB} > "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo "✅ Backup successful: $BACKUP_FILE"
    ls -lh "$BACKUP_FILE"
else
    echo "❌ Backup failed!"
    exit 1
fi
```

---

## 🐛 Common Issues

### Issue: Migration Job Fails - "table already exists"

**Symptom:**
```bash
$ docker logs migrate_job
sqlalchemy.exc.ProgrammingError: (psycopg2.errors.DuplicateTable) 
relation "route_data" already exists
```

**Cause:** Database volume persists after `docker-compose down`, but Alembic's version tracking is out of sync.

**Solution 1: Stamp Alembic (Recommended)**
```bash
# Tell Alembic the database is at the current state
docker-compose exec api alembic stamp head

# Restart migration job
docker-compose restart migrate_job
```

**Solution 2: Skip Migration**
Set the migration container to not restart on failure (already configured):
```yaml
migrate:
  restart: "no"  # Won't block other services
```

**Solution 3: Fresh Database (⚠️ DATA LOSS)**
```bash
# Backup first!
docker-compose exec db pg_dump -U ${POSTGRES_USER} -d ${POSTGRES_DB} > backup.sql

# Remove only database volume
docker-compose down
docker volume rm vtrack_postgres_data

# Recreate
docker-compose up -d
```

### Issue: Alert Processor Exits Immediately

**Symptom:**
```bash
$ docker ps -a | grep alert_processor
alert_processor   Exited (1) 2 minutes ago
```

**Check logs:**
```bash
docker logs alert_processor
```

**Common Causes:**

1. **Missing dependency** (e.g., `ModuleNotFoundError: No module named 'yaml'`)
   ```bash
   # Rebuild with updated dependencies
   docker-compose build alert-processor
   docker-compose up -d alert-processor
   ```

2. **Redis not available**
   ```bash
   # Check Redis is healthy
   docker ps | grep redis
   docker exec redis_queue redis-cli ping
   
   # Restart alert processor after Redis is ready
   docker-compose restart alert-processor
   ```

3. **Missing zones.yaml**
   ```bash
   # Check if zones.yaml is mounted correctly
   docker exec alert_processor ls -la /usr/local/lib/python3.11/site-packages/shared/
   
   # If missing, check docker-compose.yml volumes configuration
   ```

### Issue: Redis Connection Refused

**Symptom:**
```bash
redis.exceptions.ConnectionError: Error connecting to Redis
```

**Solutions:**
```bash
# Check Redis is running and healthy
docker ps | grep redis
docker logs redis_queue

# Test Redis connection
docker exec redis_queue redis-cli ping

# Restart Redis
docker-compose restart redis

# Check network connectivity
docker-compose exec api ping redis
```

### Issue: PostgreSQL Connection Failed

**Symptom:**
```bash
could not translate host name "db" to address
connection refused
```

**Solutions:**
```bash
# Check Postgres is running and healthy
docker ps | grep postgres
docker logs postgres_db

# Check health status
docker inspect postgres_db | grep -A 10 Health

# Wait for health check
docker-compose up -d db
# Wait ~10-15 seconds for health check to pass

# Restart dependent services
docker-compose restart api
```

### Issue: Port Already in Use

**Symptom:**
```bash
ERROR: for api  Cannot start service api: 
Bind for 0.0.0.0:8000 failed: port is already allocated
```

**Solutions:**
```bash
# Find what's using the port
sudo lsof -i :8000
# Or
sudo netstat -tlnp | grep :8000

# Kill the process
kill -9 <PID>

# Or change the port in docker-compose.yml
ports:
  - "8001:8000"  # Host:Container
```

### Issue: Code Changes Not Applying

**Symptom:** Made changes but container still runs old code.

**Causes & Solutions:**

1. **Not using dev mode**
   ```bash
   # Use dev mode for hot-reloading
   docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
   
   # Then just restart (no rebuild needed)
   docker restart alert_processor
   ```

2. **Docker cache**
   ```bash
   # Force rebuild without cache
   docker-compose build --no-cache alert-processor
   docker-compose up -d alert-processor
   ```

3. **Editing wrong location**
   ```bash
   # Make sure you're editing source, not container files
   # Source: ./microservices/alert-processor/main.py
   # NOT: docker exec alert_processor vim main.py
   ```

### Issue: Disk Space Full

**Symptom:**
```bash
Error: No space left on device
```

**Solutions:**
```bash
# Check Docker disk usage
docker system df

# Clean up unused images
docker image prune -a

# Clean up stopped containers
docker container prune

# Clean up unused volumes (⚠️ may delete data)
docker volume prune

# Clean everything (⚠️ DANGER)
docker system prune -a --volumes
```

---

## 🏴󠁧󠁢󠁥󠁮󠁧󠁿 Docker Compose Flags Explained

### Basic Commands

```bash
# Start services
docker-compose up -d                    # Detached mode (background)
docker-compose up                       # Foreground (see logs)

# Stop services
docker-compose stop                     # Stop containers, keep them
docker-compose down                     # Stop and remove containers/networks
docker-compose down -v                  # Stop and remove everything including volumes ⚠️
```

### Useful Flags

| Flag | Effect | Data Loss? | Use When |
|------|--------|------------|----------|
| `-d` | Detached mode | ❌ | Running in background |
| `--build` | Rebuild images | ❌ | Code/dependency changes |
| `--no-cache` | Skip Docker cache | ❌ | Cache issues or fresh build |
| `--force-recreate` | Recreate containers | ❌ | Container issues |
| `-v` | Remove volumes | ⚠️ **YES** | Complete reset needed |
| `--remove-orphans` | Remove unlisted containers | ❌ | Cleanup after compose file changes |

### Common Combinations

```bash
# Update code (no data loss)
docker-compose up -d --build

# Fresh rebuild (no data loss)
docker-compose build --no-cache
docker-compose up -d

# Fix container issues (no data loss)
docker-compose down
docker-compose up -d

# Complete reset (⚠️ DATA LOSS)
docker-compose down -v
docker-compose up -d --build

# Development mode
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Rebuild specific service
docker-compose up -d --build --no-deps alert-processor
```

---

## 🔍 Debugging Tools

### Check Service Status

```bash
# All containers
docker-compose ps

# Detailed status
docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Resource usage
docker stats --no-stream

# Service logs
docker-compose logs -f api
docker-compose logs --tail 50 alert_processor
```

### Network Debugging

```bash
# List networks
docker network ls

# Inspect network
docker network inspect vtrack_vtrack-network

# Test connectivity between services
docker-compose exec api ping redis
docker-compose exec api ping db

# Check DNS resolution
docker-compose exec api nslookup redis
```

### Database Debugging

```bash
# Connect to PostgreSQL
docker-compose exec db psql -U ${POSTGRES_USER} -d ${POSTGRES_DB}

# List tables
docker-compose exec db psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c "\dt"

# Check table contents
docker-compose exec db psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c "SELECT COUNT(*) FROM route_data;"

# Check migrations
docker-compose exec api alembic current
```

### Redis Debugging

```bash
# Check Redis is responding
docker exec redis_queue redis-cli ping

# Monitor commands
docker exec redis_queue redis-cli monitor

# Check queue lengths
docker exec redis_queue redis-cli LLEN coordinate_queue
docker exec redis_queue redis-cli LLEN alert_queue

# Peek at queue
docker exec redis_queue redis-cli LRANGE coordinate_queue 0 2
```

### Container Debugging

```bash
# Get shell in container
docker-compose exec api bash
docker-compose exec alert_processor sh  # Alpine uses sh

# Check environment variables
docker-compose exec api env | grep DATABASE

# Check file system
docker-compose exec api ls -la /app

# Check Python packages
docker-compose exec api pip list
```

---

## 📋 Troubleshooting Checklist

When something isn't working:

1. **Check all services are running**
   ```bash
   docker-compose ps
   ```

2. **Check logs for errors**
   ```bash
   docker-compose logs --tail 50
   ```

3. **Verify health checks**
   ```bash
   docker ps  # Look for "(healthy)" status
   ```

4. **Test connectivity**
   ```bash
   docker exec redis_queue redis-cli ping
   docker-compose exec api curl http://localhost:8000/docs
   ```

5. **Check resource usage**
   ```bash
   docker stats --no-stream
   df -h  # Disk space
   ```

6. **Review recent changes**
   - Did you modify docker-compose.yml?
   - Did you update dependencies?
   - Did you change environment variables?

7. **Try progressively stronger fixes**
   - Level 1: `docker-compose restart`
   - Level 2: `docker-compose up -d --build`
   - Level 3: `docker-compose down && docker-compose up -d`
   - Level 4: `docker-compose down -v` (after backup!)

---

## 🆘 Getting Help

If you're still stuck:

1. **Gather information**
   ```bash
   # Save all logs
   docker-compose logs > debug_logs.txt
   
   # System info
   docker version
   docker-compose version
   
   # Service status
   docker-compose ps -a
   ```

2. **Check documentation**
   - [Development Workflow](development/workflow.md)
   - [Database Migrations](database-migrations.md)
   - [Architecture Overview](../architecture/overview.md)

3. **Common error patterns**
   - Search logs for keywords: `ERROR`, `FAILED`, `Exception`
   - Check for port conflicts
   - Verify environment variables are set

---

## 🔗 Related Documentation

- [Quick Start Guide](../getting-started/quickstart.md) - Initial setup
- [Development Workflow](development/workflow.md) - Daily development tasks
- [Database Migrations](database-migrations.md) - Alembic troubleshooting
- [Redis Queue Guide](redis/queue-guide.md) - Redis-specific issues
- [Deployment Guide](deployment.md) - Production considerations
