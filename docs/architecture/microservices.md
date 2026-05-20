# VTrack — Microservices Reference

## Service inventory

Nine containers run under `docker-compose`. Five are **managed** (started/stopped by the conductor around collection windows). Three are **observability** (always available). One is **always-on** (the conductor itself).

| Container | Image | Managed by | Ports |
| --- | --- | --- | --- |
| `conductor` | custom | — (always-on) | — |
| `api` | custom | conductor | 8000 |
| `db` | postgres:16-alpine | conductor | 5432 |
| `redis` | redis:7-alpine | conductor | 6379 |
| `alert-processor` | custom | conductor | — |
| `notification-sender` | custom | conductor | — |
| `tempo` | grafana/tempo | — | 4317, 4318, 3200 |
| `prometheus` | prom/prometheus | — | 9090 |
| `grafana` | grafana/grafana | — | 3000 |

---

## Service details

### 1. Conductor (`microservices/conductor/`)

Always-on orchestrator. Owns the container lifecycle and emits the root OTel span for every slot.

**Architecture:** Clean Architecture — `domain/` → `adapters/` → `conductor.py` → `main.py`

**Key files:**

| File | Role |
| --- | --- |
| `conductor.py` | ReAct loop — `_startup_slot`, `_watch_slot`, `run` |
| `domain/ports.py` | `IVtrackGateway`, `IContainerGateway` ABCs |
| `domain/resource_policy.py` | `should_stop_after_slot(summary)` pure logic |
| `adapters/vtrack_gateway.py` | `HttpxVtrackGateway` — HTTP calls to vtrack |
| `adapters/container_gateway.py` | `DockerContainerGateway` — Docker SDK |
| `adapters/tracing.py` | `configure_tracing(service_name, otlp_endpoint)` |
| `main.py` | Wires OTel, `AsyncOpenTelemetryTransport`, slots, conductor |

**OTel spans emitted:**

```text
conductor.slot                {slot.name, slot.date}
  ├── conductor.container.start   {containers.count}
  ├── conductor.health.wait
  ├── conductor.guardian.activate {slot.name}
  ├── conductor.resource.eval     {resource.total_memory_mb, resource.decision}
  └── conductor.slot.watch        {slot.outcome}
```

**Tests:** 62 tests — `tests/test_conductor_otel.py`, `test_trace_propagation.py`, `test_resource_policy.py`, `test_vtrack_gateway.py`

---

### 2. vtrack API (`app/`)

FastAPI application. Handles data collection, the guardian state machine, cookie refresh, and exposes monitoring endpoints that the conductor polls.

**Architecture:** Full Clean Architecture across all layers

**Key files:**

| File | Role |
| --- | --- |
| `main.py` | FastAPI routes, lifespan, OTel + scheduler wiring |
| `scheduler.py` | `Scheduler` — guardian state machine (`_watch_slot`) |
| `scraper_async.py` | `AsyncCollectionManager` — HTTP collection loop |
| `monitoring.py` | `GET /monitor/guardian`, `POST /monitor/guardian/activate` |
| `tracing.py` | `configure_tracing(service_name, otlp_endpoint)` |
| `cookie_refresh/` | Programmed login use case (ReAct pattern, VNC browser) |
| `domain/ports.py` | `IRouteDataRepository`, `ICollectionStateStore` ABCs |
| `domain/scraper.py` | Pure functions: `parse_remote_datetime`, `normalize_route_data`, … |
| `adapters/route_repository.py` | `SqlAlchemyRouteRepository` |
| `adapters/collection_state.py` | `InMemoryCollectionState` |

**OTel spans emitted:**

```text
guardian.slot.{name}              {slot.name}
  ├── guardian.watching
  └── guardian.collection.start   {trigger}
        collection.run            {collection.task_id, collection.datapoints,
                                   collection.duration_s}
          └── cookie_refresh.run  {refresh.success, refresh.steps_taken}
```

**Tests:** 354 tests, 97% coverage

**Key endpoints:**

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Simple health check (polled by conductor) |
| `GET` | `/monitor/guardian` | Returns guardian state and last outcome |
| `POST` | `/monitor/guardian/activate` | Activates guardian for a named slot |
| `POST` | `/collect/start` | Starts data collection manually |
| `POST` | `/collect/stop` | Stops data collection |
| `GET` | `/collect/status` | Returns collection status and scheduler info |
| `POST` | `/session/set-cookies` | Injects authenticated session cookies |
| `GET` | `/session/status` | Returns session validity and expiry |

---

### 3. Alert Processor (`microservices/alert-processor/`)

Consumer service. Pops coordinates from `coordinate_queue`, runs geofence analysis, pushes alerts to `alert_queue`.

**Key files:**

| File | Role |
| --- | --- |
| `main.py` | `AlertConsumer` — `_process_coordinate_queue`, `_queue_alert` |
| `tracing.py` | `configure_tracing(service_name, otlp_endpoint)` |

**OTel spans emitted:**

```text
alert_processor.coordinate.process  {coordinate.ruta, coordinate.latitude,
                                      coordinate.longitude, alerts.generated}
  └── alert_processor.alert.queue   {alert.type, alert.zone}
```

**Tests:** 5 OTel span tests in `tests/test_alert_processor_otel.py`

**Dependencies:** `shared-package` (MessageQueue, LocationAnalyzer)

---

### 4. Notification Sender (`microservices/notification-sender/`)

Consumer service. Pops alerts from `alert_queue`, formats them, and sends Telegram messages to configured recipients.

**Key files:**

| File | Role |
| --- | --- |
| `main.py` | `NotificationConsumer` — `_process_alert_queue`, `run` |
| `tracing.py` | `configure_tracing(service_name, otlp_endpoint)` |
| `providers/telegram.py` | `TelegramNotifier` — formats and sends messages |
| `users.yaml` | Per-user Telegram IDs and roles (`admin` / `user`) |
| `config.py` | `Settings` (pydantic-settings) — `REDIS_URL`, `TELEGRAM_BOT_TOKEN` |

**OTel spans emitted:**

```text
notification_sender.alert.send  {alert.ruta, alert.type,
                                  notification.provider, notification.success}
```

**Tests:** 6 OTel span tests in `tests/test_notification_sender_otel.py`

---

### 5. Shared Package (`shared-package/`)

Python package installed into every service container at build time.

| Module | Contents |
| --- | --- |
| `shared/message_queue.py` | `MessageQueue` — `push_coordinate`, `pop_coordinate`, `push_alert`, `pop_alert`, `health_check` |
| `shared/location_alerts.py` | `LocationAnalyzer`, `LocationAlert`, `AlertType`, `Zone` |
| `shared/zones.yaml` | Geofence zone definitions (zone_id, name, lat, lon, radius_meters) |

---

### 6. Observability stack

All four application services export OTLP traces directly to Tempo over gRPC. No collector needed.

**Tempo** (`docker/tempo/tempo.yaml`):

- OTLP gRPC receiver on port 4317
- OTLP HTTP receiver on port 4318
- Local trace storage at `/tmp/tempo`
- HTTP API for Grafana on port 3200

**Prometheus** (`docker/prometheus/prometheus.yml`):

- Scrapes `api:8000/metrics` every 15 s
- Port 9090

**Grafana** (`docker/grafana/provisioning/`):

- Tempo datasource pre-provisioned (default)
- Prometheus datasource pre-provisioned
- Anonymous access enabled for local development
- Port 3000

---

## Communication patterns

### HTTP (conductor → vtrack)

```text
conductor  ──[POST /monitor/guardian/activate]──►  vtrack
           ◄──[GET  /monitor/guardian          ]──
           ◄──[GET  /monitor/health            ]──
```

W3C `traceparent` header is injected by `AsyncOpenTelemetryTransport` (httpx) on every outgoing request from conductor, continuing the `conductor.slot` trace into vtrack.

### Redis queues

```text
vtrack  ──[LPUSH coordinate_queue]──►  Redis  ──[RPOP]──►  alert-processor
alert-processor  ──[LPUSH alert_queue]──►  Redis  ──[RPOP]──►  notification-sender
```

### Docker socket

```text
conductor  ──[Docker SDK]──►  /var/run/docker.sock
```

Container start/stop/stats operations. The conductor's container mounts the socket read-write.

---

## Environment variables

| Variable | Services | Purpose |
| --- | --- | --- |
| `REDIS_URL` | api, alert-processor, notification-sender | Redis connection string |
| `DATABASE_URL` | api | PostgreSQL connection string |
| `TELEGRAM_BOT_TOKEN` | notification-sender | Telegram Bot API token |
| `OTLP_ENDPOINT` | api, conductor, alert-processor, notification-sender | OTLP gRPC endpoint (default `http://tempo:4317`) |
| `VTRACK_BASE_URL` | conductor | Base URL for vtrack HTTP calls (default `http://api:8000`) |
| `MANAGED_CONTAINERS` | conductor | Comma-separated list of container names to manage |
| `SLOT_MORNING_WINDOW_OPEN` | conductor | e.g. `05:00` |
| `SLOT_AFTERNOON_WINDOW_OPEN` | conductor | e.g. `14:30` |
| `MEMORY_THRESHOLD_MB` | conductor | Stop-after-slot threshold in MB (default `256`) |
| `LOGIN_EMAIL`, `LOGIN_PASSWORD` | api | Scraper credentials for remote GPS API |

---

## File structure

```text
vtrack/
├── app/                            # vtrack FastAPI application
│   ├── main.py
│   ├── scheduler.py
│   ├── scraper_async.py
│   ├── monitoring.py
│   ├── tracing.py
│   ├── models.py
│   ├── database.py
│   ├── config.py
│   ├── cookie_refresh/
│   │   └── __init__.py             # run_refresh() use case
│   ├── domain/
│   │   ├── scraper.py
│   │   └── ports.py
│   ├── adapters/
│   │   ├── route_repository.py
│   │   ├── collection_state.py
│   │   └── collection_status_adapter.py
│   └── tests/                      # 354 tests
│
├── microservices/
│   ├── conductor/
│   │   ├── conductor.py
│   │   ├── domain/
│   │   │   ├── ports.py
│   │   │   └── resource_policy.py
│   │   ├── adapters/
│   │   │   ├── vtrack_gateway.py
│   │   │   ├── container_gateway.py
│   │   │   └── tracing.py
│   │   ├── main.py
│   │   ├── requirements.txt
│   │   └── tests/                  # 62 tests
│   │
│   ├── alert-processor/
│   │   ├── main.py
│   │   ├── tracing.py
│   │   ├── requirements.txt
│   │   └── tests/
│   │
│   └── notification-sender/
│       ├── main.py
│       ├── tracing.py
│       ├── config.py
│       ├── users.yaml
│       ├── providers/
│       │   └── telegram.py
│       ├── requirements.txt
│       └── tests/
│
├── shared-package/
│   └── src/shared/
│       ├── message_queue.py
│       ├── location_alerts.py
│       └── zones.yaml
│
├── docker/
│   ├── tempo/tempo.yaml
│   ├── prometheus/prometheus.yml
│   └── grafana/provisioning/
│       └── datasources/datasources.yaml
│
└── docker-compose.yml
```

---

## Dependency rules (enforced)

No service imports code from another service. All cross-service communication is through:

1. **Redis queues** — coordinate and alert messages (shared schema in `shared-package`)
2. **HTTP** — conductor calls vtrack monitoring endpoints only
3. **Docker socket** — conductor manages container lifecycle only

The `shared-package` is the only shared code dependency, and it contains only pure data structures and Redis abstractions — no business logic specific to any single service.
