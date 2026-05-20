# VTrack — Architecture Quick Reference

## Service map

```text
always-on
  conductor          :  container lifecycle + OTel root span per slot

managed (started/stopped by conductor around collection windows)
  api                :  8000   FastAPI — collection, guardian, cookie refresh
  db                 :  5432   PostgreSQL — tasks, route entries
  redis              :  6379   queues: coordinate_queue, alert_queue
  alert-processor    :  —      geofence detection consumer
  notification-sender:  —      Telegram delivery consumer

observability (independent, always up)
  tempo              :  4317 (OTLP gRPC)  4318 (OTLP HTTP)  3200 (HTTP API)
  prometheus         :  9090
  grafana            :  3000
```

---

## Collection window schedule (America/Bogota)

| Slot | Opens | Closes |
| --- | --- | --- |
| morning | 05:00 | 06:40 |
| afternoon | 14:30 | 16:30 |

---

## OTel span quick-lookup

| Span name | Service | Key attributes |
| --- | --- | --- |
| `conductor.slot` | conductor | `slot.name`, `slot.date` |
| `conductor.container.start` | conductor | `containers.count` |
| `conductor.health.wait` | conductor | — |
| `conductor.guardian.activate` | conductor | `slot.name` |
| `conductor.resource.eval` | conductor | `resource.total_memory_mb`, `resource.decision` |
| `conductor.slot.watch` | conductor | `slot.outcome` |
| `guardian.slot.{name}` | vtrack | `slot.name` |
| `guardian.watching` | vtrack | — |
| `guardian.collection.start` | vtrack | `trigger` |
| `collection.run` | vtrack | `collection.task_id`, `collection.datapoints`, `collection.duration_s` |
| `cookie_refresh.run` | vtrack | `refresh.success`, `refresh.steps_taken` |
| `alert_processor.coordinate.process` | alert-processor | `coordinate.ruta`, `coordinate.latitude`, `coordinate.longitude`, `alerts.generated` |
| `alert_processor.alert.queue` | alert-processor | `alert.type`, `alert.zone` |
| `notification_sender.alert.send` | notification-sender | `alert.ruta`, `alert.type`, `notification.provider`, `notification.success` |

---

## Key files by concern

### Container lifecycle

| File | What it does |
| --- | --- |
| `microservices/conductor/conductor.py` | `_startup_slot`, `_watch_slot`, `run` |
| `microservices/conductor/domain/ports.py` | `IVtrackGateway`, `IContainerGateway` |
| `microservices/conductor/adapters/vtrack_gateway.py` | HTTP calls to vtrack |
| `microservices/conductor/adapters/container_gateway.py` | Docker SDK |
| `microservices/conductor/main.py` | Wires OTel, slots, conductor |

### Guardian + collection

| File | What it does |
| --- | --- |
| `app/scheduler.py` | Guardian state machine (`IDLE → WATCHING → STARTED/MISSED`) |
| `app/scraper_async.py` | `AsyncCollectionManager` — polls remote GPS API |
| `app/monitoring.py` | `GET /monitor/guardian`, `POST /monitor/guardian/activate` |
| `app/cookie_refresh/__init__.py` | `run_refresh()` — programmed VNC login |

### Domain logic

| File | What it does |
| --- | --- |
| `app/domain/scraper.py` | `parse_remote_datetime`, `normalize_route_data`, `should_start/stop_collection` |
| `app/domain/ports.py` | `IRouteDataRepository`, `ICollectionStateStore`, `CollectionSnapshot` |
| `microservices/conductor/domain/resource_policy.py` | `should_stop_after_slot(summary)` |
| `shared-package/src/shared/location_alerts.py` | `LocationAnalyzer`, `LocationAlert`, `Zone` |

### Adapters (port implementations)

| File | Port it implements |
| --- | --- |
| `app/adapters/route_repository.py` | `IRouteDataRepository` (SQLAlchemy) |
| `app/adapters/collection_state.py` | `ICollectionStateStore` (in-memory) |
| `microservices/conductor/adapters/vtrack_gateway.py` | `IVtrackGateway` (httpx) |
| `microservices/conductor/adapters/container_gateway.py` | `IContainerGateway` (Docker SDK) |

### OTel infrastructure

| File | What it does |
| --- | --- |
| `app/tracing.py` | `configure_tracing("vtrack", endpoint)` |
| `microservices/conductor/adapters/tracing.py` | `configure_tracing("conductor", endpoint)` |
| `microservices/alert-processor/tracing.py` | `configure_tracing("alert-processor", endpoint)` |
| `microservices/notification-sender/tracing.py` | `configure_tracing("notification-sender", endpoint)` |
| `docker/tempo/tempo.yaml` | OTLP receiver + local storage |
| `docker/prometheus/prometheus.yml` | Scrapes vtrack `/metrics` |
| `docker/grafana/provisioning/datasources/` | Tempo + Prometheus datasources |

---

## Useful commands

### Observability

```bash
# View a slot's full trace in Grafana
open http://localhost:3000
# Explore → Tempo → Search → service.name = "conductor"

# Check all spans from alert-processor
# Explore → Tempo → Search → service.name = "alert-processor"
```

### Collection control

```bash
# Check guardian state
curl http://localhost:8000/monitor/guardian

# Manually start collection (conductor does this automatically in-window)
curl -X POST http://localhost:8000/collect/start

# Check collection status
curl http://localhost:8000/collect/status

# Session status (scraper cookies)
curl http://localhost:8000/session/status
```

### Conductor logs

```bash
docker logs -f conductor
# Shows slot timing, container start/stop decisions, health wait, resource eval
```

### Queue inspection

```bash
# Queue lengths
docker exec redis_queue redis-cli LLEN coordinate_queue
docker exec redis_queue redis-cli LLEN alert_queue

# Peek at contents (does not remove)
docker exec redis_queue redis-cli LRANGE coordinate_queue 0 4
docker exec redis_queue redis-cli LRANGE alert_queue 0 4
```

### Tests

```bash
# vtrack (354 tests)
pytest app/tests/ -v --cov=app --cov-report=term-missing

# Conductor (62 tests)
cd microservices/conductor && python -m pytest tests/ -v

# Alert processor (5 OTel tests)
cd microservices/alert-processor && python -m pytest tests/ -v

# Notification sender OTel (6 tests)
cd microservices/notification-sender && python -m pytest tests/test_notification_sender_otel.py -v
```

---

## Clean Architecture dependency rule

```text
infrastructure   main.py, docker-compose.yml, tracing.py
      ↓ imports
  adapters        route_repository, container_gateway, vtrack_gateway, …
      ↓ imports
  application     scraper_async, scheduler, conductor, AlertConsumer, …
      ↓ imports
   domain         ports, resource_policy, scraper (pure Python, no I/O)
```

Nothing in domain or application imports from adapters or infrastructure. OTel API (`from opentelemetry import trace`) is allowed in application; SDK and exporters only in infrastructure.

---

## Guardian state machine

```text
IDLE  ──(window_open)──►  WATCHING  ──(already_running)──►  STARTED
                                    ──(grace_exceeded)────►  STARTED
                                    ──(window_close, no start)──►  MISSED
```

Activated by `POST /monitor/guardian/activate?slot=morning`. State returned on `GET /monitor/guardian`.

---

## Further reading

- [Architecture overview](overview.md) — container lifecycle, trace topology, data flow, design decisions
- [Microservices reference](microservices.md) — per-service detail, endpoints, environment variables, file structure
- [Redis queue guide](../guides/redis/queue-guide.md) — queue internals and monitoring
- [Alert processor guide](../guides/alert-processor.md) — consumer loop deep dive
- [Development workflow](../guides/development/workflow.md) — local dev, hot reload, debugging
