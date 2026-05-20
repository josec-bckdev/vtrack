# VTrack — Architecture Overview

## Services at a glance

| Container | `restart` | Role |
| --- | --- | --- |
| `conductor` | `always` | Owns container lifecycle; never stops |
| `api` (fastapi_api) | `no` | vtrack FastAPI app — collection, guardian, cookie refresh |
| `db` (postgres_db) | `no` | PostgreSQL — persistent coordinate and task storage |
| `redis` (redis_queue) | `no` | Redis — `coordinate_queue` and `alert_queue` FIFO lists |
| `alert-processor` | `no` | Geofence detection — pops coordinates, pushes alerts |
| `notification-sender` | `no` | Telegram delivery — pops alerts, sends messages |
| `tempo` | `no` | Grafana Tempo — OTLP gRPC receiver + trace storage |
| `prometheus` | `no` | Prometheus — scrapes vtrack `/metrics` |
| `grafana` | `no` | Grafana — traces (Tempo) + metrics (Prometheus) dashboards |

The five managed services (`api`, `db`, `redis`, `alert-processor`, `notification-sender`) are started and stopped by the conductor around two daily collection windows. Observability services run independently.

---

## Container lifecycle (conductor)

The conductor is the always-on orchestrator. It runs a ReAct loop that owns every transition:

```text
On conductor startup
  ├── inside a collection window?
  │     yes → _startup_slot (start stack, health wait, activate guardian)
  │     no  → stop any managed containers that are running
  └── enter main loop

Main loop (per slot)
  sleep until window_open
  │
  ├── conductor.container.start   start all 5 managed containers
  ├── conductor.health.wait       poll GET /monitor/health until 200
  ├── conductor.guardian.activate POST /monitor/guardian/activate  ← traceparent injected here
  ├── conductor.resource.eval     query Docker stats for all containers
  └── conductor.slot.watch        poll GET /monitor/guardian every 30 s
        │                           until task_running == false
        │
        └── (optional) stop all managed containers if memory > threshold
```

**Slot windows (America/Bogota):**

| Slot | Opens | Closes |
| --- | --- | --- |
| morning | 05:00 | 06:40 |
| afternoon | 14:30 | 16:30 |

---

## Guardian state machine (vtrack)

Inside the vtrack process, `app/scheduler.py` runs one `_watch_slot` coroutine per slot. It is a state machine that fires collection within the window:

```text
IDLE
  │  clock reaches window_open
  ▼
WATCHING
  │  poll every 30 s
  ├── already_running?    → STARTED  (guardian.collection.start trigger=already_running)
  └── grace_period ends?  → start()  → STARTED  (trigger=grace_exceeded)

STARTED  ←─ set when collection.run span ends
MISSED   ←─ set when window closes with no collection started
```

Guardian state is exposed on `GET /monitor/guardian` (polled by conductor) and activated via `POST /monitor/guardian/activate`.

---

## Data flow

### Collection cycle

```text
1.  Conductor activates guardian via HTTP (W3C traceparent header injected)
2.  Guardian fires collection — AsyncCollectionManager.start()
3.  Collection loop polls remote GPS API every ~15 s
4.  For each coordinate batch:
      a. Normalize and persist to PostgreSQL (RouteDataEntry)
      b. Push to Redis: LPUSH coordinate_queue <json>
5.  alert-processor polls: RPOP coordinate_queue
6.  LocationAnalyzer checks coordinate against all zones
7.  On geofence entry/exit: push to Redis: LPUSH alert_queue <json>
8.  notification-sender polls: RPOP alert_queue
9.  TelegramNotifier.send_alert() → Telegram Bot API → users
10. Collection stops (manually or on scraper logic) — AsyncCollectionManager.stop()
    → collection.run span ends with datapoints + duration_s attributes
```

### Cookie refresh (inside vtrack)

When the scraper session expires, `cookie_refresh.run` fires inside the `collection.run` trace:

```text
collection.run span (open)
  └── cookie_refresh.run span
        FileProgrammedScriptStore loads steps
        VncBrowserGateway executes login steps inside VNC container
        DirectVtrackGateway pushes extracted cookies to /session/set-cookies
        span.set_attribute("refresh.success", result.success)
        span.set_attribute("refresh.steps_taken", result.steps_taken)
```

---

## Distributed trace topology

```text
[conductor]
  conductor.slot                    {slot.name, slot.date}
    ├── conductor.container.start   {containers.count}
    ├── conductor.health.wait
    ├── conductor.guardian.activate {slot.name}    ← W3C traceparent injected via httpx
    ├── conductor.resource.eval     {resource.total_memory_mb, resource.decision}
    └── conductor.slot.watch        {slot.outcome}

[vtrack — same trace, continued from traceparent header]
  guardian.slot.{name}              {slot.name}
    ├── guardian.watching
    └── guardian.collection.start   {trigger}
          collection.run            {collection.task_id, collection.datapoints,
                                     collection.duration_s}
            └── cookie_refresh.run  {refresh.success, refresh.steps_taken}

[alert-processor — independent root span, correlate by slot.date in Grafana]
  alert_processor.coordinate.process  {coordinate.ruta, coordinate.latitude,
                                        coordinate.longitude, alerts.generated}
    └── alert_processor.alert.queue   {alert.type, alert.zone}

[notification-sender — independent root span, correlate by alert.ruta + alert.type]
  notification_sender.alert.send      {alert.ruta, alert.type,
                                        notification.provider, notification.success}
```

Conductor → vtrack: W3C `traceparent` header injected by `AsyncOpenTelemetryTransport` (httpx); extracted automatically by `opentelemetry-instrumentation-fastapi`.

Alert-processor and notification-sender do not receive HTTP requests during normal operation, so they emit independent root spans. Correlate them in Grafana by filtering on `slot.date`.

---

## Clean Architecture layers

Every bounded context follows the same dependency rule — inner layers never import from outer layers:

```text
infrastructure (main.py, Dockerfile)
      │
  adapters/ (tracing.py, vtrack_gateway.py, route_repository.py, …)
      │
  application/ (conductor.py, scheduler.py, scraper_async.py, AlertConsumer, …)
      │
   domain/ (ports.py, resource_policy.py, scraper.py)
```

**OTel placement rule:**

| Layer | Allowed |
| --- | --- |
| `domain/` | nothing |
| `application/` | `from opentelemetry import trace` — API only (no SDK) |
| `adapters/tracing.py` | SDK + OTLP exporter — `configure_tracing()` only |
| `infrastructure/main.py` | calls `configure_tracing(service_name, endpoint)` |

This means all application-layer code is a zero-cost no-op when no provider is configured, and all tests that don't need spans never touch the SDK.

---

## Port and adapter inventory

### vtrack (`app/domain/ports.py`)

| Port | Adapter | Purpose |
| --- | --- | --- |
| `IRouteDataRepository` | `SqlAlchemyRouteRepository` | DB persistence for collection tasks and route entries |
| `ICollectionStateStore` | `InMemoryCollectionState` | In-process state (status, counters, deduplication hash) |
| `ICollectionStatusAdapter` | `AsyncCollectionManagerAdapter` | Narrow bridge: guardian → collection manager |

### conductor (`microservices/conductor/domain/ports.py`)

| Port | Adapter | Purpose |
| --- | --- | --- |
| `IVtrackGateway` | `HttpxVtrackGateway` | HTTP calls to vtrack `/monitor/*` endpoints |
| `IContainerGateway` | `DockerContainerGateway` | Docker container start/stop/stats via Docker SDK |

---

## Redis message schema

### `coordinate_queue` (FIFO — LPUSH / RPOP)

```json
{
  "ruta": 101,
  "latitude": 4.7110,
  "longitude": -74.0059,
  "position_ts": "2026-05-19T05:30:00-05:00",
  "route_status": "En recorrido",
  "queued_at": "2026-05-19T05:30:01-05:00"
}
```

### `alert_queue` (FIFO — LPUSH / RPOP)

```json
{
  "ruta": 101,
  "latitude": 4.7110,
  "longitude": -74.0059,
  "alert_type": "GEOFENCE_ENTRY",
  "area_name": "North Terminal",
  "severity": "WARNING",
  "timestamp": "2026-05-19T05:31:00-05:00"
}
```

> **Note:** `severity` is scheduled for deprecation. It is already omitted from all OTel span attributes.

---

## Health checks

| Service | Check |
| --- | --- |
| `db` | `pg_isready -U $POSTGRES_USER -d $POSTGRES_DB` |
| `redis` | `redis-cli ping` |
| `api` | `GET /monitor/health` → 200 (polled by conductor) |
| `alert-processor` | log output + queue statistics |
| `notification-sender` | log output |

---

## Startup sequence

```text
docker-compose up -d
│
├── tempo, prometheus, grafana start (no dependencies)
├── redis starts → health check passes
├── db starts → health check passes
└── conductor starts (restart: always)
      │
      ├── if inside window: _startup_slot → start api, db, redis, alert-processor, notification-sender
      └── if outside window: stop any managed containers already running
```

The managed services are **not** started by `docker-compose up` directly — they start when conductor decides the time is right. Set `restart: "no"` on all five so Docker never auto-restarts them outside conductor's control.

---

## Key architectural decisions

**Why conductor instead of cron or `restart: always` on managed services?**
The collection window is narrow (90 minutes, twice a day). Running PostgreSQL, Redis, and two worker services 24/7 wastes resources and increases failure surface. The conductor gives fine-grained start/stop control, includes a memory-threshold gate, and emits a full OTel trace for every slot.

**Why Redis Lists instead of Pub/Sub?**
Lists persist messages when the consumer is down. Queue backlog is inspectable (`LRANGE`), recoverable, and trivially scalable (add more consumers). Pub/Sub would drop messages if the consumer missed the window.

**Why independent root spans for alert-processor and notification-sender?**
These services consume from Redis queues; there is no HTTP call that carries a `traceparent` header. Modifying the Redis message schema to include a trace context would couple tracing concerns into the domain model. Independent spans correlated by `slot.date` in Grafana is a cleaner separation.

**Why `opentelemetry-api` only in application layers?**
The API package is a pure façade — it is a no-op when no provider is configured. This keeps unit tests fast (no SDK overhead) and keeps the SDK out of domain and application code, which should not know about infrastructure concerns like exporters or batch processors.
