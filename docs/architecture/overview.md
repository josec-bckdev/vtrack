# VTrack Architecture Overview - Complete Picture

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          DOCKER COMPOSE ORCHESTRATION                        │
│                                                                               │
│  ┌────────────────────────┐  ┌────────────────────────┐  ┌───────────────┐ │
│  │   Container: fastapi_api│  │ Container: alert_processor│ │ Container:  │ │
│  │   Image: custom         │  │ Image: custom           │  │ redis:7     │ │
│  │   Port: 8000           │  │ No exposed ports        │  │ Port: 6379  │ │
│  │                         │  │                         │  │             │ │
│  │  ┌─────────────────┐   │  │  ┌─────────────────┐   │  │  ┌────────┐ │ │
│  │  │ app/main.py     │   │  │  │ main.py         │   │  │  │ Redis  │ │ │
│  │  │ FastAPI app     │   │  │  │ AlertConsumer   │   │  │  │ Server │ │ │
│  │  └────────┬────────┘   │  │  └────────┬────────┘   │  │  └───┬────┘ │ │
│  │           │             │  │           │             │  │      │      │ │
│  │  ┌────────▼────────┐   │  │  ┌────────▼────────┐   │  │  ┌───▼────┐ │ │
│  │  │scraper_async.py │   │  │  │shared/          │   │  │  │ Lists: │ │ │
│  │  │Data collector   │   │  │  │message_queue.py │   │  │  │- coord │ │ │
│  │  └────────┬────────┘   │  │  │location_alerts  │   │  │  │- alert │ │ │
│  │           │             │  │  └────────┬────────┘   │  │  └───▲────┘ │ │
│  │  ┌────────▼────────┐   │  │           │             │  │      │      │ │
│  │  │shared/          │   │  │           │             │  │      │      │ │
│  │  │message_queue.py │   │  │           │             │  │      │      │ │
│  │  └────────┬────────┘   │  │           │             │  │      │      │ │
│  │           │             │  │           │             │  │      │      │ │
│  │           │ LPUSH       │  │           │ RPOP        │  │      │      │ │
│  │           └─────────────┼──┼───────────┴─────────────┼──┼──────┘      │ │
│  │                         │  │                         │  │             │ │
│  └─────────────────────────┘  └─────────────────────────┘  └─────────────┘ │
│            ▲                              │                       ▲          │
│            │ HTTP requests                │ Reads from            │          │
│            │ Port 8000                    │ coordinate_queue      │          │
│            │                              │ Writes to alert_queue │          │
└────────────┼──────────────────────────────┼───────────────────────┼──────────┘
             │                              │                       │
             │                              │                       │
  ┌──────────▼───────┐         ┌───────────▼────────┐    ┌────────▼────────┐
  │   User/Client    │         │  Geofence Logic    │    │  Your Dev Tools │
  │                  │         │  ┌──────────────┐  │    │  ┌────────────┐ │
   │  curl/browser    │         │  │ Boyaca       │  │    │  │redis_      │ │
   │  /collection/    │         │  │ (4.742, -74.06)│ │    │  │monitor.py  │ │
   │  start           │         │  │ radius: 1600m│  │    │  └────────────┘ │
   └──────────────────┘         │  └──────────────┘  │    │  ┌────────────┐ │
                                                │  ┌──────────────┐  │    │  │test_alert_ │ │
                                                │  │Prado Zone   │  │    │  │processor.py│ │
                                                │  │(4.718, -74.06)│ │    │  └────────────┘ │
                                                │  │radius: 1200m│  │    │  ┌────────────┐ │
                                                │  └──────────────┘  │    │  │redis-cli   │ │
                                └────────────────────┘    └─────────────────┘
```

## 🔄 Data Flow - Complete Cycle

### Phase 1: Data Collection (Producer)

```
1. User triggers: curl -X POST http://localhost:8000/collection/start
                       ↓
2. FastAPI endpoint: POST /collection/start
                       ↓
3. scraper_async.py: AsyncCollectionManager.start_collection()
                       ↓
4. Polls remote API every 15 seconds
                       ↓
5. For each coordinate:
   - Save to PostgreSQL
   - Push to Redis: message_queue.push_coordinate()
                       ↓
6. Redis: LPUSH coordinate_queue <json_data>
```

### Phase 2: Queue Storage (Redis)

```
Redis List: coordinate_queue

[newest] ← LPUSH adds here
   │
   ├── {"ruta": 103, "lat": 4.72, "lon": -74.01, "queued_at": "..."}
   │
   ├── {"ruta": 102, "lat": 4.71, "lon": -74.00, "queued_at": "..."}
   │
   ├── {"ruta": 101, "lat": 4.70, "lon": -73.99, "queued_at": "..."}
   │
[oldest] ← RPOP removes from here
```

### Phase 3: Processing (Consumer)

```
1. alert-processor main.py runs: while True
                       ↓
2. Poll Redis: coordinate = redis.rpop('coordinate_queue')
                       ↓
3. If coordinate exists:
   - Extract: ruta, latitude, longitude
                       ↓
4. LocationAnalyzer.analyze_coordinate(ruta, lat, lon)
   - Check against all zones
   - Compare with previous position (tracking_state)
   - Detect entry/exit events
                       ↓
5. If zone entry/exit detected:
   - Create LocationAlert object
                       ↓
6. Push alert: message_queue.push_alert()
                       ↓
7. Redis: LPUSH alert_queue <alert_json>
                       ↓
8. Sleep 1 second, loop back to step 1
```

### Phase 4: Alert Storage (Redis)

```
Redis List: alert_queue

[newest] ← LPUSH adds here
   │
   ├── {"ruta": 101, "alert_type": "GEOFENCE_ENTRY", "area": "Boyaca", ...}
   │
   ├── {"ruta": 102, "alert_type": "GEOFENCE_EXIT", "area": "Depot", ...}
   │
[oldest] ← Ready for downstream processing (future: notifications, dashboard, etc.)
```

## 🎯 Key Components Explained

### 1. FastAPI Container (Producer)
**Purpose:** Main application, data collection
**Runs:** `python -m uvicorn app.main:app --reload`
**Key Files:**
- `app/main.py` - FastAPI routes
- `app/scraper_async.py` - Collects coordinates from remote API
- `app/models.py` - Database models
- `shared/message_queue.py` - Redis client

**Docker Settings:**
```yaml
restart: always              # Auto-restart on failure
ports: ["8000:8000"]        # Expose HTTP API
volumes:                     # Hot reload enabled
  - ./app:/app/app
  - ./shared-package:/app/shared-package
depends_on: [db, redis]     # Wait for dependencies
```

### 2. Alert Processor Container (Consumer)
**Purpose:** Process coordinates, generate geofence alerts
**Runs:** `python main.py`
**Key Files:**
- `microservices/alert-processor/main.py` - Consumer loop
- `shared/message_queue.py` - Redis client
- `shared/location_alerts.py` - Geofence logic

**Docker Settings:**
```yaml
restart: always              # Auto-restart on failure
depends_on: [redis]          # Only needs Redis
environment:
  REDIS_URL: redis://redis:6379/0
  PYTHONUNBUFFERED: 1        # Real-time logging
```

### 3. Redis Container (Message Broker)
**Purpose:** Queue coordination between producer and consumer
**Runs:** `redis-server`
**Data Structures:**
- `coordinate_queue` - LIST (FIFO)
- `alert_queue` - LIST (FIFO)

**Docker Settings:**
```yaml
image: redis:7-alpine        # Lightweight Redis
ports: ["6379:6379"]         # Expose for monitoring
volumes:
  - redis_data:/data         # Persistent storage
```

### 4. PostgreSQL Container (Not Shown in Queue Flow)
**Purpose:** Persistent storage for coordinates
**Stores:** Historical coordinate data, route information

### 5. Shared Package
**Purpose:** Code reuse across services
**Contains:**
- `message_queue.py` - Redis operations (push/pop)
- `location_alerts.py` - Geofence logic, Zone definitions, AlertTypes

**Installed in both containers during build:**
```dockerfile
COPY shared-package /app/shared-package
RUN pip install /app/shared-package
```

## 🔧 Development Tools You Have

### Monitoring Tools
```bash
# 1. Redis queue monitor (visual)
python redis_monitor.py --interval 1

# 2. Redis CLI (direct access)
docker exec -it redis_queue redis-cli

# 3. Container logs
docker logs -f alert_processor
docker logs -f fastapi_api
```

### Testing Tools
```bash
# 1. Test alert processor
python test_alert_processor.py --scenario zone

# 2. Manual coordinate push
docker exec redis_queue redis-cli LPUSH coordinate_queue '{...}'

# 3. Load testing
python test_alert_processor.py --load 1000
```

### Development Tools
```bash
# 1. Hot reload mode
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# 2. Quick restart
docker restart alert_processor

# 3. Rebuild after changes
docker-compose build alert-processor
```

## 🚀 Startup Sequence

When you run `docker-compose up`:

```
1. Networks created: vtrack-network (bridge)
2. Volumes created: postgres_data, redis_data, pgadmin_data
3. Containers start in dependency order:

   Start: redis (no dependencies)
   ├─ Health check: redis-cli ping
   └─ ✓ Ready

   Start: db/postgres (no dependencies)
   ├─ Health check: pg_isready
   └─ ✓ Ready

   Start: migrate (depends on db)
   ├─ Wait for db health check
   ├─ Run: alembic upgrade head
   └─ ✓ Exit (one-time migration)

   Start: api (depends on db, redis)
   ├─ Wait for db & redis health checks
   ├─ Run: uvicorn app.main:app
   └─ ✓ Listening on :8000

   Start: alert-processor (depends on redis)
   ├─ Wait for redis health check
   ├─ Run: python main.py
   ├─ Connect to Redis
   ├─ Initialize LocationAnalyzer
   └─ ✓ Start consuming loop

   Start: pgadmin (depends on db)
   └─ ✓ Admin interface on :8080
```

## 💡 Independence and Failure Handling

### Scenario 1: Alert Processor Crashes
```
FastAPI (still running) → Redis (queuing) → Alert Processor (CRASHED ❌)
                           ↓
                     Coordinates pile up in Redis
                           ↓
                     Docker restarts alert-processor (restart: always)
                           ↓
                     Alert Processor processes backlog
                           ✓ No data lost!
```

### Scenario 2: Redis Crashes
```
FastAPI → Redis (CRASHED ❌) ← Alert Processor
   ↓                              ↓
Coordinates saved to DB     Waiting, will retry
   ✓ Data safe!             ✓ Will reconnect!

Docker restarts Redis (restart: always)
   ↓
Both services reconnect automatically
   ✓ System resumes!
```

### Scenario 3: You Stop Alert Processor for Development
```
FastAPI → Redis → Alert Processor (STOPPED ⏸️ by you)
   ↓         ↓
   ✓      Coordinates queue up

You make changes, restart:
   ↓
Alert Processor → Processes entire backlog
   ✓ Caught up!
```

## 🎓 Key Architectural Decisions

1. **Why Redis Lists instead of Pub/Sub?**
   - Persistence: Messages stay in queue even if consumer is down
   - Simplicity: LPUSH/RPOP is easy to understand
   - Backlog: Can see queue size and items
   - Multiple consumers: Can scale by adding more consumers

2. **Why Separate Containers?**
   - Independence: Restart one without affecting others
   - Scalability: Can run multiple alert-processors
   - Development: Test each component independently
   - Deployment: Deploy updates without downtime

3. **Why Shared Package?**
   - DRY: Single source of truth for common code
   - Consistency: Same geofence logic everywhere
   - Updates: Change once, affects all services

4. **Why Docker Compose?**
   - Orchestration: Manages multiple services
   - Networking: Automatic service discovery
   - Dependencies: Handles startup order
   - Development: Matches production closely

## 📚 Documentation Map

```
├─ ARCHITECTURE_OVERVIEW.md (this file) ← Start here
│
├─ REDIS_QUEUE_GUIDE.md ─── Redis internals, queue operations
│  └─ REDIS_QUICK_REFERENCE.md ─── Quick command reference
│
├─ ALERT_PROCESSOR_GUIDE.md ─── Consumer deep dive
│  └─ DEV_WORKFLOW.md ─── Development workflows
│
├─ redis_monitor.py ─── Monitoring tool
└─ test_alert_processor.py ─── Testing tool
```

## 🎯 Next Steps

1. **Understand the flow** - Read this diagram thoroughly
2. **Test it** - Use `test_alert_processor.py --scenario zone`
3. **Monitor it** - Run `python redis_monitor.py`
4. **Modify it** - Follow `DEV_WORKFLOW.md`
5. **Deploy it** - Use existing `docker-compose up`

**You now have a complete understanding of the VTrack microservices architecture!** 🎉
