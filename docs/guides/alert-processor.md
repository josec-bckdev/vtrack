# Alert Processor Consumer - Complete Guide

## 🔍 How the Alert Processor Runs

### Startup Flow

```
docker-compose up
       ↓
Reads docker-compose.yml (lines 117-133)
       ↓
Builds container from microservices/alert-processor/Dockerfile
       ↓
Dockerfile executes: CMD ["python", "main.py"]
       ↓
main.py runs: AlertConsumer().start(poll_interval=1)
       ↓
Infinite loop starts:
    while True:
        coordinate = redis.rpop('coordinate_queue')
        if coordinate:
            analyze and generate alerts
        sleep(1 second)
```

### What Actually Runs

**It's just a Python script in a Docker container!** Think of it as:

```python
# This is essentially what happens:
if __name__ == "__main__":
    consumer = AlertConsumer()
    consumer.start(poll_interval=1)  # ← Runs forever in a while True loop
```

Docker keeps it alive with:
- `restart: always` - If it crashes, Docker restarts it automatically
- `PYTHONUNBUFFERED=1` - See logs in real-time (no buffering)

### It's NOT a daemon in the traditional sense
- **No systemd/supervisor** - Docker itself is the "daemon manager"
- **No background process** - It runs in the foreground inside the container
- **Completely independent** - Separate container, separate process, separate network

## 🏗️ Architecture Independence

```
┌─────────────────────┐       ┌─────────────────────┐
│  fastapi_api        │       │  alert_processor    │
│  (Container 1)      │       │  (Container 2)      │
│                     │       │                     │
│  scraper_async.py   │       │  main.py            │
│       ↓             │       │       ↓             │
│  lpush() ───────────┼──────▶│  rpop()             │
│                     │  Redis│       ↓             │
│                     │       │  analyze()          │
│                     │  Queue│       ↓             │
│                     │◀──────┼─  lpush() alerts    │
└─────────────────────┘       └─────────────────────┘
     Independent                   Independent
   Can restart/stop              Can restart/stop
   without affecting             without affecting
     the other one                  the other one
```

**Key Point:** They only communicate through Redis queues. Restarting one doesn't affect the other!

## ✅ YES - You Can Restart It Independently!

### Option 1: Restart the Container (Quick)

```bash
# Restart just the alert-processor (FastAPI keeps running)
docker restart alert_processor

# Verify it restarted
docker ps | grep alert_processor

# Watch it come back online
docker logs -f alert_processor
```

**What Happens:**
1. Container stops (Python process exits)
2. Any coordinate being processed is **not lost** (it wasn't popped from Redis yet)
3. Container restarts
4. Python script runs again from the beginning
5. Starts consuming from where it left off

### Option 2: Stop, Modify Code, Rebuild, Start (For Code Changes)

```bash
# 1. Stop the alert-processor
docker stop alert_processor

# 2. Make your code changes (see below)
vim microservices/alert-processor/main.py
# OR
vim shared-package/src/shared/location_alerts.py

# 3. Rebuild just the alert-processor image
docker-compose build alert-processor

# 4. Start it again
docker-compose up -d alert-processor

# 5. Watch logs to see your changes
docker logs -f alert_processor
```

### Option 3: Hot Reload Development Mode (Advanced)

For rapid development, mount the code as a volume:

```yaml
# Add to docker-compose.yml under alert-processor:
volumes:
  - ./microservices/alert-processor:/app
  - ./shared-package:/app/shared-package
```

Then changes are live, but you still need to restart the container to reload Python.

## 🧪 Testing Workflow - Make Changes and Test

### Full Testing Example

Let's say you want to **add logging** when a coordinate is processed:

#### Step 1: Stop the consumer
```bash
docker stop alert_processor
```

#### Step 2: Make your change
```bash
# Edit the main.py file
vim microservices/alert-processor/main.py
```

Add this at line 103 (after extracting coordinate data):

```python
logger.info(f"🔍 Processing Ruta {ruta} at ({latitude}, {longitude})")
```

#### Step 3: Rebuild and start
```bash
# Rebuild the image
docker-compose build alert-processor

# Start it
docker-compose up -d alert_processor

# Watch logs with your new logging
docker logs -f alert_processor
```

#### Step 4: Test with a manual push
```bash
# Push a test coordinate
docker exec redis_queue redis-cli LPUSH coordinate_queue '{
  "ruta": 999,
  "latitude": 4.7110,
  "longitude": -74.0059,
  "position_ts": "2026-02-10T14:30:45-05:00",
  "route_status": "Test",
  "student_status": "Test",
  "queued_at": "2026-02-10T14:30:45-05:00"
}'

# You should see in the logs:
# INFO - 🔍 Processing Ruta 999 at (4.7110, -74.0059)
```

## 🎯 Common Modifications and Testing

### Scenario 1: Change Geofence Zones

**File to edit:** `shared-package/src/shared/location_alerts.py`

**Example:** Add a new danger zone:

```python
# Around line 90 in location_alerts.py, add:
Zone(
    zone_id=4,
    name="New Danger Area",
    latitude=4.6500,      # ← Your coordinates
    longitude=-74.0700,
    radius_meters=500,
    alert_type=AlertType.GEOFENCE_ENTRY,
    severity=AlertSeverity.CRITICAL
),
```

**Test it:**
```bash
# 1. Rebuild (shared package changed)
docker-compose build alert-processor

# 2. Restart
docker-compose up -d alert_processor

# 3. Push a coordinate in that zone
docker exec redis_queue redis-cli LPUSH coordinate_queue '{
  "ruta": 101,
  "latitude": 4.6500,
  "longitude": -74.0700
}'

# 4. Check for alert in logs
docker logs alert_processor | grep "New Danger Area"
# Should see: [ALERT] Route 101: GEOFENCE_ENTRY in New Danger Area - Severity: CRITICAL
```

### Scenario 2: Change Processing Interval

**File to edit:** `microservices/alert-processor/main.py`

**Example:** Process every 5 seconds instead of 1:

```python
# Around line 178 in main.py, change:
consumer.start(poll_interval=5)  # Changed from 1 to 5
```

**Test it:**
```bash
# Rebuild and restart
docker-compose build alert-processor && docker-compose up -d alert-processor

# Watch logs - you'll see it processes slower
docker logs -f alert_processor
```

### Scenario 3: Add Custom Alert Logic

**File to edit:** `shared-package/src/shared/location_alerts.py`

**Example:** Alert if route moves too fast:

```python
def analyze_coordinate(self, ruta: int, latitude: float, longitude: float) -> List[LocationAlert]:
    """Analyze a coordinate and generate alerts if needed."""
    alerts = []

    route_key = f"ruta_{ruta}"
    current_zones = []

    # NEW: Check if moved too fast
    prev_state = self.tracking_state.get(route_key, {})
    if prev_state:
        prev_lat = prev_state.get('last_lat')
        prev_lon = prev_state.get('last_lon')
        prev_time = prev_state.get('last_update')

        if prev_lat and prev_lon and prev_time:
            from geopy.distance import geodesic
            distance = geodesic((prev_lat, prev_lon), (latitude, longitude)).meters
            time_diff = (datetime.now(ZoneInfo("America/Bogota")) - prev_time).total_seconds()

            if time_diff > 0:
                speed_mps = distance / time_diff  # meters per second
                speed_kmh = speed_mps * 3.6

                if speed_kmh > 100:  # Over 100 km/h
                    alert = LocationAlert(
                        ruta=ruta,
                        latitude=latitude,
                        longitude=longitude,
                        alert_type=AlertType.UNUSUAL_LOCATION,
                        zone_name="Speed Check",
                        severity=AlertSeverity.WARNING,
                        timestamp=datetime.now(ZoneInfo("America/Bogota")),
                        message=f"Route {ruta} traveling at {speed_kmh:.1f} km/h"
                    )
                    alerts.append(alert)

    # ... rest of existing code
```

**Test it:**
```bash
# Rebuild
docker-compose build alert-processor && docker-compose up -d alert-processor

# Push two coordinates far apart quickly
docker exec redis_queue redis-cli LPUSH coordinate_queue '{"ruta":101,"latitude":4.6000,"longitude":-74.0000}'
sleep 2
docker exec redis_queue redis-cli LPUSH coordinate_queue '{"ruta":101,"latitude":4.7000,"longitude":-74.0500}'

# Check for speed alert
docker logs alert_processor | tail -20
```

## 🔄 Development Workflow Comparison

### Without Volumes (Current Setup)
```
Edit code → Build image → Restart container → Test
     ↓           ↓              ↓              ↓
  30 sec     1-2 min         5 sec         Instant
```

**Total time per iteration: ~2-3 minutes**

### With Volumes (Faster Development)
```yaml
# Add to docker-compose.yml
alert-processor:
  volumes:
    - ./microservices/alert-processor:/app
    - ./shared-package:/app/shared-package
  # Add this for auto-reload (optional)
  command: python -u main.py
```

```
Edit code → Restart container → Test
     ↓              ↓              ↓
  30 sec         5 sec         Instant
```

**Total time per iteration: ~35 seconds**

**No rebuild needed!** Just restart the container to reload Python.

## 📊 Monitoring During Development

Open 4 terminals for full visibility:

```bash
# Terminal 1: Monitor Redis queues
python redis_monitor.py --interval 1

# Terminal 2: Watch alert-processor logs
docker logs -f alert_processor

# Terminal 3: Watch FastAPI logs (optional)
docker logs -f fastapi_api

# Terminal 4: Push test data and run commands
docker exec redis_queue redis-cli LPUSH coordinate_queue '...'
```

## 🛠️ Troubleshooting

### Consumer not processing after restart
```bash
# Check if it's running
docker ps | grep alert_processor

# Check logs for errors
docker logs alert_processor

# Check Redis connection
docker exec alert_processor python -c "
import redis
r = redis.from_url('redis://redis:6379/0')
print('Connected:', r.ping())
"
```

### Changes not taking effect
```bash
# Force rebuild without cache
docker-compose build --no-cache alert-processor

# Remove old image
docker rmi $(docker images | grep alert-processor | awk '{print $3}')

# Rebuild and start fresh
docker-compose up -d --build alert-processor
```

### Want to run multiple consumers (scale)
```bash
# Run 3 alert-processor instances (they'll share the work)
docker-compose up -d --scale alert-processor=3

# Check all instances
docker ps | grep alert_processor

# Watch logs from all instances
docker logs -f alert_processor
```

## 🎓 Key Takeaways

1. **Alert-processor is just a Python script** running in a Docker container
2. **Completely independent from FastAPI** - Restart one without affecting the other
3. **Communication only through Redis** - Decoupled architecture
4. **Restart anytime** - Coordinates stay in Redis, no data loss
5. **Easy to test** - Stop, modify, rebuild, start, push test data
6. **Can scale** - Run multiple consumers for higher throughput
7. **Docker manages restarts** - `restart: always` keeps it alive

## 🚀 Quick Reference Commands

```bash
# View status
docker ps | grep alert_processor

# View logs
docker logs -f alert_processor

# Restart
docker restart alert_processor

# Stop
docker stop alert_processor

# Start
docker start alert_processor

# Rebuild after code changes
docker-compose build alert-processor
docker-compose up -d alert-processor

# Check it's processing
docker logs alert_processor | grep "Processed"

# Push test coordinate
docker exec redis_queue redis-cli LPUSH coordinate_queue '{"ruta":999,"latitude":4.71,"longitude":-74.00}'
```

## 📚 Next Steps

- Try modifying the geofence zones
- Add custom logging to understand the flow
- Implement your own alert logic
- Test with manual coordinate pushes
- Monitor with the redis_monitor.py tool

The beauty of this architecture: **You can experiment freely without breaking the data collection!** 🎉
