# Redis Queue Quick Reference Card

## 🚀 Quick Start

### Check if Redis is running
```bash
docker ps | grep redis_queue
```

### Connect to Redis CLI
```bash
docker exec -it redis_queue redis-cli
```

### Use Python monitor (recommended)
```bash
# Install redis-py if needed
pip install redis

# Run the monitor
python redis_monitor.py

# Or with custom settings
python redis_monitor.py --interval 1 --peek 10
```

## 📋 Essential Redis Commands

| What you want to do | Command |
|---------------------|---------|
| **Check queue size** | `LLEN coordinate_queue` |
| **Peek at newest item** | `LINDEX coordinate_queue 0` |
| **Peek at next to process** | `LINDEX coordinate_queue -1` |
| **View first 10 items** | `LRANGE coordinate_queue 0 9` |
| **View last 10 items** | `LRANGE coordinate_queue -10 -1` |
| **Monitor in real-time** | `MONITOR` |
| **Clear a queue** | `DEL coordinate_queue` |
| **Clear everything** | `FLUSHDB` |
| **Check memory usage** | `INFO memory` |
| **List all keys** | `KEYS *` |

## 🔍 Monitoring Commands

### Check queue lengths from host
```bash
# Coordinate queue
docker exec redis_queue redis-cli LLEN coordinate_queue

# Alert queue
docker exec redis_queue redis-cli LLEN alert_queue
```

### Continuously watch queue size
```bash
watch -n 1 'docker exec redis_queue redis-cli LLEN coordinate_queue'
```

### Peek at next coordinate to be processed
```bash
docker exec redis_queue redis-cli LINDEX coordinate_queue -1
```

### Peek at most recent alert
```bash
docker exec redis_queue redis-cli LINDEX alert_queue 0
```

### Watch consumer logs
```bash
docker logs -f alert_processor
```

### Watch producer logs
```bash
docker logs -f fastapi_api | grep coordinate
```

## 🧪 Testing Commands

### Manually push a test coordinate
```bash
docker exec redis_queue redis-cli LPUSH coordinate_queue '{
  "ruta": 999,
  "latitude": 4.7110,
  "longitude": -74.0059,
  "position_ts": "2026-02-10T14:30:45-05:00",
  "route_status": "Test",
  "student_status": "Test",
  "queued_at": "2026-02-10T14:30:45-05:00"
}'
```

Watch the alert-processor consume it:
```bash
docker logs -f alert_processor
```

### Simulate load
```bash
# Push 100 test coordinates
for i in {1..100}; do
  docker exec redis_queue redis-cli LPUSH coordinate_queue "{\"ruta\":$i,\"latitude\":4.71,\"longitude\":-74.00}"
done

# Watch queue drain
watch -n 0.5 'docker exec redis_queue redis-cli LLEN coordinate_queue'
```

## 🛠️ Troubleshooting

### Queue is growing (not being consumed)
```bash
# Check if consumer is running
docker ps | grep alert_processor

# Check consumer logs for errors
docker logs alert_processor --tail 50

# Restart consumer
docker restart alert_processor
```

### Queue is empty (not being produced)
```bash
# Check if API is running
docker ps | grep fastapi_api

# Check if scraping is active
curl http://localhost:8000/collection/status

# Check API logs
docker logs fastapi_api --tail 50 | grep coordinate
```

### Redis connection issues
```bash
# Test Redis connectivity
docker exec redis_queue redis-cli ping
# Should return: PONG

# Check Redis logs
docker logs redis_queue

# Restart Redis (will clear queues!)
docker restart redis_queue
```

## 📊 Data Flow Visualization

```
Producer Flow:
  scraper_async.py
       ↓
  message_queue.push_coordinate()
       ↓
  LPUSH coordinate_queue
       ↓
  [Redis stores in memory]

Consumer Flow:
  alert_processor continuously polls
       ↓
  RPOP coordinate_queue
       ↓
  analyze_coordinate()
       ↓
  LPUSH alert_queue (if alert generated)
```

## 🎯 Common Scenarios

### Scenario 1: Watch the system in action
```bash
# Terminal 1: Monitor queues
python redis_monitor.py

# Terminal 2: Watch consumer
docker logs -f alert_processor

# Terminal 3: Start data collection
curl -X POST http://localhost:8000/collection/start
```

### Scenario 2: Debug why alerts aren't being generated
```bash
# 1. Push a test coordinate in a known geofence zone
docker exec redis_queue redis-cli LPUSH coordinate_queue '{
  "ruta": 101,
  "latitude": 4.7110,
  "longitude": -74.0059,
  "route_status": "Test"
}'

# 2. Watch consumer process it
docker logs -f alert_processor

# 3. Check alert queue
docker exec redis_queue redis-cli LRANGE alert_queue 0 -1
```

### Scenario 3: Clear queues and start fresh
```bash
# Clear both queues
docker exec redis_queue redis-cli DEL coordinate_queue
docker exec redis_queue redis-cli DEL alert_queue

# Verify they're empty
docker exec redis_queue redis-cli LLEN coordinate_queue
docker exec redis_queue redis-cli LLEN alert_queue
```

## 📚 Learn More

- Full guide: [REDIS_QUEUE_GUIDE.md](queue-guide.md)
- Redis commands: https://redis.io/commands/
- Python redis library: https://redis-py.readthedocs.io/

## 💡 Pro Tips

1. **Use the Python monitor** - It's easier to read than raw Redis CLI
2. **Monitor in one terminal, logs in another** - See cause and effect
3. **Test with manual pushes** - Isolate issues between producer and consumer
4. **Watch queue lengths** - If growing = consumer problem, if empty = producer problem
5. **Use MONITOR sparingly** - It shows ALL commands and can slow down Redis

## 🔐 Production Considerations

- Enable Redis persistence (RDB/AOF)
- Set up Redis authentication
- Configure memory limits
- Monitor with proper tools (Prometheus, Grafana)
- Consider Redis Cluster for high availability
- Use Redis Streams instead of lists for better features
