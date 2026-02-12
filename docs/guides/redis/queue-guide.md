# Redis Queue Guide - VTrack Real-Time Monitoring

## 🏗️ Architecture Overview

### How Data Flows Through Redis

```
┌─────────────────────────────────────────────────────────────────┐
│  PRODUCER: scraper_async.py (FastAPI container)                 │
│  ┌────────────────────────────────────────────────────────┐    │
│  │ 1. Scrapes coordinate from remote API                   │    │
│  │ 2. Saves to PostgreSQL                                  │    │
│  │ 3. Calls: message_queue.push_coordinate()               │    │
│  │    → redis_client.lpush('coordinate_queue', json_data)  │    │
│  └────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ LPUSH (adds to front of list)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  REDIS (In-Memory Data Store)                   │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  Key: "coordinate_queue"                                │    │
│  │  Type: LIST                                             │    │
│  │  Storage: RAM (+ optional disk persistence)            │    │
│  │                                                          │    │
│  │  Data Structure:                                        │    │
│  │  [newest] ← lpush adds here                            │    │
│  │    ├─ {"ruta": 101, "latitude": 4.71, ...}            │    │
│  │    ├─ {"ruta": 102, "latitude": 4.72, ...}            │    │
│  │    ├─ {"ruta": 101, "latitude": 4.73, ...}            │    │
│  │  [oldest] ← rpop removes from here                     │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Volume: /data (mapped to redis_data Docker volume)            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ RPOP (removes from end of list)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  CONSUMER: alert-processor microservice                         │
│  ┌────────────────────────────────────────────────────────┐    │
│  │ 1. Polls: coordinate = message_queue.pop_coordinate()  │    │
│  │    → redis_client.rpop('coordinate_queue')             │    │
│  │ 2. Analyzes: location_analyzer.analyze_coordinate()    │    │
│  │ 3. If alert triggered → push to 'alert_queue'          │    │
│  │    → redis_client.lpush('alert_queue', alert_json)     │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Runs in a loop: while True: process() → sleep(1 sec)          │
└─────────────────────────────────────────────────────────────────┘
```

## 📦 Where Data is Stored

### In-Memory Storage
Redis stores all data **in RAM** for ultra-fast access:
- **Container:** `redis_queue` (redis:7-alpine image)
- **Port:** 6379 (accessible at `localhost:6379` from host)
- **Database:** 0 (Redis has 16 databases, we use DB 0)
- **Data Structure:** Redis LIST (ordered collection)

### Persistent Storage (Optional)
- **Docker Volume:** `redis_data`
- **Mount Point:** `/data` inside container
- **Purpose:** Redis can periodically save snapshots to disk for crash recovery
- **Default:** Redis 7 uses RDB snapshots (saves to dump.rdb)

## 🔍 How to Inspect Redis Queues

### Method 1: Using redis-cli (Command Line Interface)

#### Connect to Redis container
```bash
# From host machine
docker exec -it redis_queue redis-cli

# You'll see:
# 127.0.0.1:6379>
```

#### Check queue lengths
```redis
# Check coordinate queue length
LLEN coordinate_queue

# Check alert queue length
LLEN alert_queue

# Example output:
# (integer) 42
```

#### Peek at queue contents (without removing)
```redis
# View first 10 items in coordinate_queue (newest)
LRANGE coordinate_queue 0 9

# View last 10 items in coordinate_queue (oldest, next to be consumed)
LRANGE coordinate_queue -10 -1

# View all items (careful with large queues!)
LRANGE coordinate_queue 0 -1

# View first item in alert_queue
LRANGE alert_queue 0 0
```

#### Example output
```json
1) "{\"ruta\": 101, \"latitude\": 4.7110, \"longitude\": -74.0059, \"position_ts\": \"2026-02-10T14:30:45-05:00\", \"route_status\": \"En Servicio\", \"student_status\": \"Activo\", \"queued_at\": \"2026-02-10T14:30:45.123456-05:00\"}"
```

#### Monitor queue activity in real-time
```redis
# Watch all commands happening on Redis
MONITOR

# You'll see live output like:
# 1707587445.123456 [0 172.18.0.3:52134] "LPUSH" "coordinate_queue" "{\"ruta\":101...}"
# 1707587446.234567 [0 172.18.0.4:52135] "RPOP" "coordinate_queue"
# 1707587447.345678 [0 172.18.0.4:52135] "LPUSH" "alert_queue" "{\"ruta\":101...}"
```

#### Check memory usage
```redis
# Get Redis memory statistics
INFO memory

# Get specific queue memory usage
MEMORY USAGE coordinate_queue
```

#### Clear queues (for testing)
```redis
# Delete all items from coordinate queue
DEL coordinate_queue

# Delete all items from alert queue
DEL alert_queue

# Delete everything in Redis (use with caution!)
FLUSHDB
```

#### Exit redis-cli
```redis
EXIT
```

### Method 2: Using Python Script (Programmatic Access)

Create a monitoring script:

```python
# redis_monitor.py
import redis
import json
import time
from datetime import datetime

# Connect to Redis
r = redis.from_url("redis://localhost:6379/0", decode_responses=True)

def monitor_queues():
    """Monitor Redis queues in real-time"""
    print("🔍 Redis Queue Monitor - Press Ctrl+C to stop\n")

    try:
        while True:
            # Get queue lengths
            coord_len = r.llen('coordinate_queue')
            alert_len = r.llen('alert_queue')

            # Get memory info
            memory = r.info('memory')
            used_memory_human = memory['used_memory_human']

            # Clear screen (optional)
            print(f"\n{'='*60}")
            print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*60}")
            print(f"📊 Coordinate Queue: {coord_len} items")
            print(f"🚨 Alert Queue: {alert_len} items")
            print(f"💾 Redis Memory Usage: {used_memory_human}")

            # Peek at next coordinate to be processed
            if coord_len > 0:
                next_coord = r.lindex('coordinate_queue', -1)  # Last item (will be popped next)
                if next_coord:
                    data = json.loads(next_coord)
                    print(f"\n📍 Next coordinate to process:")
                    print(f"   Ruta: {data.get('ruta')}")
                    print(f"   Location: ({data.get('latitude')}, {data.get('longitude')})")
                    print(f"   Queued at: {data.get('queued_at')}")

            # Peek at latest alert
            if alert_len > 0:
                latest_alert = r.lindex('alert_queue', 0)  # First item (newest)
                if latest_alert:
                    data = json.loads(latest_alert)
                    print(f"\n🚨 Latest alert:")
                    print(f"   Ruta: {data.get('ruta')}")
                    print(f"   Type: {data.get('alert_type')}")
                    print(f"   Area: {data.get('area_name')}")
                    print(f"   Severity: {data.get('severity')}")

            time.sleep(2)  # Update every 2 seconds

    except KeyboardInterrupt:
        print("\n\n👋 Monitoring stopped")

if __name__ == "__main__":
    monitor_queues()
```

Run it:
```bash
# Install redis-py if not installed
pip install redis

# Run the monitor
python redis_monitor.py
```

### Method 3: Using Docker Logs (See Consumer Activity)

```bash
# Watch alert-processor logs in real-time
docker logs -f alert_processor

# You'll see output like:
# 2026-02-10 14:30:45 - INFO - Processed 100 coordinates, Generated 3 alerts
# 2026-02-10 14:30:47 - WARNING - [ALERT] Route 101: GEOFENCE_ENTRY in Boyaca - Severity: WARNING
```

```bash
# Watch FastAPI logs (producer)
docker logs -f fastapi_api | grep "coordinate"

# You'll see:
# DEBUG - Pushed coordinate to queue: Ruta 101 at (4.7110, -74.0059)
```

### Method 4: Using Redis Desktop Client (GUI)

Install a Redis GUI tool:
- **RedisInsight** (Official, free): https://redis.io/insight/
- **Another Redis Desktop Manager**: https://github.com/qishibo/AnotherRedisDesktopManager

Connect to:
- Host: `localhost`
- Port: `6379`
- Database: `0`

You can visually browse keys, view queue contents, and monitor in real-time.

## 🔄 How the Consumer Works

### Code Flow in alert-processor

```python
# From microservices/alert-processor/main.py

class AlertConsumer:
    def start(self, poll_interval: int = 1):
        """Start consuming coordinates"""
        while self.is_running:
            self._process_coordinate_queue()  # ← Process one coordinate
            time.sleep(poll_interval)         # ← Wait 1 second

    def _process_coordinate_queue(self):
        # Step 1: Pop coordinate from Redis
        coordinate = self.message_queue.pop_coordinate()
        #          └─→ redis_client.rpop('coordinate_queue')
        #              Returns: {"ruta": 101, "latitude": 4.71, ...} or None

        if coordinate:
            # Step 2: Extract data
            ruta = coordinate.get('ruta')
            latitude = coordinate.get('latitude')
            longitude = coordinate.get('longitude')

            # Step 3: Analyze with geofencing
            alerts = self.location_analyzer.analyze_coordinate(
                ruta=ruta,
                latitude=latitude,
                longitude=longitude
            )
            # ↑ Checks if route entered/exited predefined zones

            # Step 4: Push any alerts back to Redis
            for alert in alerts:
                self.message_queue.push_alert(...)
                #                └─→ redis_client.lpush('alert_queue', ...)
```

### Why This Pattern Works

1. **Decoupling**: Producer (scraper) and consumer (alert-processor) don't know about each other
2. **Buffering**: If consumer is slow, coordinates queue up in Redis
3. **Reliability**: If consumer crashes, coordinates remain in Redis
4. **Scalability**: Can run multiple alert-processor instances (they'll share the work)
5. **Simplicity**: Just a list with LPUSH (add) and RPOP (remove)

## 🧪 Testing the Queue System

### 1. Check if services are running
```bash
docker ps | grep -E "redis|alert_processor|fastapi"
```

### 2. Verify Redis connectivity
```bash
docker exec redis_queue redis-cli ping
# Should return: PONG
```

### 3. Check initial queue state
```bash
docker exec redis_queue redis-cli LLEN coordinate_queue
docker exec redis_queue redis-cli LLEN alert_queue
```

### 4. Trigger data collection (producer)
```bash
# Call your API endpoint that starts scraping
curl -X POST http://localhost:8000/collection/start
```

### 5. Watch queues fill up
```bash
# In one terminal: monitor coordinate queue
watch -n 1 'docker exec redis_queue redis-cli LLEN coordinate_queue'

# In another terminal: watch alert queue
watch -n 1 'docker exec redis_queue redis-cli LLEN alert_queue'

# In another terminal: watch consumer logs
docker logs -f alert_processor
```

### 6. Manually push a test coordinate
```bash
docker exec redis_queue redis-cli LPUSH coordinate_queue '{"ruta":101,"latitude":4.7110,"longitude":-74.0059,"position_ts":"2026-02-10T14:30:45-05:00","route_status":"En Servicio","student_status":"Activo","queued_at":"2026-02-10T14:30:45-05:00"}'
```

Watch the consumer process it immediately in the logs!

## 📊 Key Redis Commands Reference

| Command | Purpose | Example |
|---------|---------|---------|
| `LLEN key` | Get list length | `LLEN coordinate_queue` |
| `LPUSH key value` | Add to front | `LPUSH coordinate_queue '{"ruta":101}'` |
| `RPOP key` | Remove from end | `RPOP coordinate_queue` |
| `LRANGE key start stop` | View range | `LRANGE coordinate_queue 0 9` |
| `LINDEX key index` | View single item | `LINDEX coordinate_queue 0` |
| `DEL key` | Delete queue | `DEL coordinate_queue` |
| `KEYS pattern` | Find keys | `KEYS *queue*` |
| `MONITOR` | Watch all commands | `MONITOR` |
| `INFO memory` | Memory stats | `INFO memory` |
| `FLUSHDB` | Clear database | `FLUSHDB` |

## 🎯 Common Scenarios

### Queue is growing but not being consumed
```bash
# Check if alert-processor is running
docker ps | grep alert_processor

# Check alert-processor logs for errors
docker logs alert_processor

# Restart alert-processor
docker restart alert_processor
```

### Queue is empty but should have data
```bash
# Check if scraper is pushing data
docker logs fastapi_api | grep "Pushed coordinate"

# Check Redis connection from API
docker exec fastapi_api python -c "import redis; r=redis.from_url('redis://redis:6379/0'); print(r.ping())"
```

### Too many items in queue (backlog)
```bash
# Scale up consumers (run multiple alert-processors)
docker-compose up -d --scale alert-processor=3

# Or clear old data
docker exec redis_queue redis-cli DEL coordinate_queue
```

## 🔐 Redis Persistence Configuration

To ensure data survives Redis restarts, configure RDB snapshots:

```bash
# Connect to Redis
docker exec -it redis_queue redis-cli

# Configure snapshot every 60 seconds if at least 1 key changed
CONFIG SET save "60 1"

# View current save configuration
CONFIG GET save

# Force a snapshot now
BGSAVE
```

## 📚 Learning Resources

- **Redis Commands**: https://redis.io/commands/
- **Redis Lists**: https://redis.io/docs/data-types/lists/
- **Redis Pub/Sub** (alternative pattern): https://redis.io/docs/manual/pubsub/
- **Redis Streams** (more advanced queuing): https://redis.io/docs/data-types/streams/

---

**Pro Tip**: For production, consider using Redis Streams instead of lists - they provide better features for message queuing (consumer groups, acknowledgments, message history).
