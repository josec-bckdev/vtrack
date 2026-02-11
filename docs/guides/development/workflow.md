# Development Workflow - Alert Processor

## 🚀 Quick Start Development Setup

### Option 1: Standard Mode (Rebuild Required)
```bash
# Make code changes
vim microservices/alert-processor/main.py

# Rebuild and restart
docker-compose build alert-processor
docker-compose up -d alert-processor

# Watch logs
docker logs -f alert_processor
```

**Time per iteration:** ~2-3 minutes (includes rebuild)

### Option 2: Hot-Reload Mode (Faster!)
```bash
# Start with development overrides
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Make code changes
vim microservices/alert-processor/main.py

# Just restart (no rebuild needed!)
docker restart alert_processor

# Watch logs
docker logs -f alert_processor
```

**Time per iteration:** ~10 seconds (no rebuild!)

## 📋 Complete Development Cycle

### Setup (One Time)

```bash
# 1. Create alias for convenience
echo "alias dcdev='docker-compose -f docker-compose.yml -f docker-compose.dev.yml'" >> ~/.bashrc
source ~/.bashrc

# 2. Start services in dev mode
dcdev up -d

# 3. Verify services are running
docker ps
```

### Daily Workflow

#### Terminal Setup (4 terminals recommended)
```bash
# Terminal 1: Watch alert-processor logs
docker logs -f alert_processor

# Terminal 2: Monitor Redis queues
python redis_monitor.py --interval 1

# Terminal 3: Your code editor
vim microservices/alert-processor/main.py

# Terminal 4: Test commands
python test_alert_processor.py --scenario zone
```

## 🔧 Common Development Tasks

### Task 1: Add a New Geofence Zone

#### Step 1: Edit the code
```bash
vim shared-package/src/shared/location_alerts.py
```

Add around line 118:
```python
Zone(
    zone_id=4,
    name="My Test Zone",
    latitude=4.6500,
    longitude=-74.0700,
    radius_meters=500,
    alert_type=AlertType.GEOFENCE_ENTRY,
    severity=AlertSeverity.INFO
),
```

#### Step 2: Restart consumer
```bash
# With dev mode (volumes mounted)
docker restart alert_processor

# OR without dev mode (requires rebuild)
docker-compose build alert-processor && docker-compose up -d alert-processor
```

#### Step 3: Test it
```bash
# Push a coordinate in the zone
python test_alert_processor.py --scenario zone

# OR manually
docker exec redis_queue redis-cli LPUSH coordinate_queue '{
  "ruta": 101,
  "latitude": 4.6500,
  "longitude": -74.0700
}'

# Watch for alert in logs
docker logs alert_processor | grep "My Test Zone"
```

### Task 2: Add Custom Logging

#### Step 1: Add logging to consumer
```bash
vim microservices/alert-processor/main.py
```

Add at line 95 (in `_process_coordinate_queue`):
```python
logger.info(f"🔍 Analyzing Ruta {ruta} at ({latitude:.4f}, {longitude:.4f})")
```

#### Step 2: Restart
```bash
docker restart alert_processor
```

#### Step 3: Test and see logs
```bash
# Terminal 1: Watch logs
docker logs -f alert_processor

# Terminal 2: Push test data
python test_alert_processor.py --scenario batch

# You'll see:
# INFO - 🔍 Analyzing Ruta 101 at (4.6500, -74.0900)
# INFO - 🔍 Analyzing Ruta 102 at (4.6510, -74.0910)
```

### Task 3: Change Processing Logic

#### Example: Skip coordinates older than 5 minutes

```bash
vim microservices/alert-processor/main.py
```

Add at line 87 (after extracting coordinate data):
```python
# Check age of coordinate
queued_at_str = coordinate.get('queued_at')
if queued_at_str:
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    queued_at = datetime.fromisoformat(queued_at_str)
    age = datetime.now(ZoneInfo("America/Bogota")) - queued_at

    if age > timedelta(minutes=5):
        logger.warning(f"⏰ Skipping old coordinate (age: {age.total_seconds():.0f}s)")
        return
```

Restart and test:
```bash
docker restart alert_processor

# Push old coordinate (won't be processed)
docker exec redis_queue redis-cli LPUSH coordinate_queue '{
  "ruta": 101,
  "latitude": 4.65,
  "longitude": -74.09,
  "queued_at": "2026-02-10T10:00:00-05:00"
}'

# Should see: "⏰ Skipping old coordinate"
```

## 🧪 Testing Strategies

### Strategy 1: Unit Testing Changes
```bash
# Test specific functionality
python test_alert_processor.py --scenario single    # Basic processing
python test_alert_processor.py --scenario zone      # Geofence alerts
python test_alert_processor.py --scenario batch     # Multiple coordinates
```

### Strategy 2: Load Testing
```bash
# Push many coordinates to test performance
python test_alert_processor.py --load 100

# Watch processing rate in another terminal
watch -n 1 'docker exec redis_queue redis-cli LLEN coordinate_queue'
```

### Strategy 3: Integration Testing
```bash
# Start scraping (FastAPI)
curl -X POST http://localhost:8000/collection/start

# Watch everything work together
# Terminal 1: API logs
docker logs -f fastapi_api

# Terminal 2: Consumer logs
docker logs -f alert_processor

# Terminal 3: Queue monitor
python redis_monitor.py
```

## 🐛 Debugging

### View Current State
```bash
# Check queues
python test_alert_processor.py --scenario status

# Check consumer status
docker ps | grep alert_processor

# Check for errors
docker logs alert_processor | grep -i error
```

### Consumer Not Processing?
```bash
# Check if running
docker ps | grep alert_processor

# Check logs
docker logs alert_processor --tail 50

# Restart
docker restart alert_processor

# If still not working, rebuild
docker-compose build alert-processor
docker-compose up -d alert-processor
```

### No Alerts Being Generated?
```bash
# Check if coordinates are being processed
docker logs alert_processor | grep "Processed"

# Check zone definitions
docker exec alert_processor python -c "
from shared.location_alerts import LocationAnalyzer
analyzer = LocationAnalyzer()
print('Zones:', [z.name for z in analyzer.zones])
"

# Test with manual coordinate in a zone
python test_alert_processor.py --scenario zone
```

### Code Changes Not Applying?
```bash
# Make sure you're editing the right file
ls -la microservices/alert-processor/main.py
ls -la shared-package/src/shared/location_alerts.py

# Force rebuild without cache
docker-compose build --no-cache alert-processor
docker-compose up -d alert-processor

# Or use dev mode with volumes
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

## 📊 Performance Monitoring

### Check Processing Rate
```bash
# Watch queue drain
watch -n 1 'docker exec redis_queue redis-cli LLEN coordinate_queue'

# View processing stats in logs
docker logs alert_processor | grep "Processed"
```

### Memory Usage
```bash
# Check container memory
docker stats alert_processor --no-stream

# Check Redis memory
docker exec redis_queue redis-cli INFO memory | grep used_memory_human
```

## 🎯 Best Practices

### 1. Always Watch Logs During Development
```bash
# Keep a terminal open with logs
docker logs -f alert_processor
```

### 2. Use Dev Mode for Rapid Iteration
```bash
# Start with dev overrides
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# No rebuilds needed, just restart
docker restart alert_processor
```

### 3. Test with Manual Pushes First
```bash
# Before relying on scraper, test with manual data
python test_alert_processor.py --scenario zone
```

### 4. Check Queue State Regularly
```bash
# Monitor queues
python redis_monitor.py --interval 1 --peek 5
```

### 5. Commit Often
```bash
# After each working feature
git add microservices/alert-processor/
git commit -m "feat(alert-processor): add speed alert logic"
```

## 🚀 Deployment Checklist

Before deploying changes:

- [ ] Test with manual coordinates
- [ ] Test with batch processing
- [ ] Test integration with scraper
- [ ] Check logs for errors
- [ ] Verify alerts are generated correctly
- [ ] Check queue processing rate
- [ ] Test restart behavior
- [ ] Document any new configuration

## 🔗 Quick Command Reference

```bash
# Start dev mode
dcdev up -d

# Restart after changes
docker restart alert_processor

# Watch logs
docker logs -f alert_processor

# Test geofence
python test_alert_processor.py --scenario zone

# Monitor queues
python redis_monitor.py

# Stop everything
docker-compose down

# Clean rebuild
docker-compose build --no-cache alert-processor
docker-compose up -d alert-processor
```

## 📚 Related Documentation

- [ALERT_PROCESSOR_GUIDE.md](../alert-processor.md) - Complete guide
- [REDIS_QUEUE_GUIDE.md](../redis/queue-guide.md) - Redis queue details
- [REDIS_QUICK_REFERENCE.md](../redis/quick-reference.md) - Quick commands

---

**Happy coding! 🎉** Remember: The beauty of this architecture is you can break the consumer without affecting data collection!
