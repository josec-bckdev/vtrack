# vtrack — refactor session 2026-05-19

## Goal

Separate concerns across the vtrack app to make it more dynamic and expandable.
Three incremental refactors, each committed following strict TDD + Commitizen rules.

---

## Work completed

### `refactor(scheduler)` — extract scheduler class to app/scheduler.py

- `Scheduler` class moved out of `app/main.py` into `app/scheduler.py`
- `app/main.py` is now responsible only for FastAPI routes and lifespan wiring
- Fixed test patches in `test_schedule_config.py`: `app.main.datetime` → `app.scheduler.datetime`

### `refactor(domain)` — extract pure functions to app/domain/

- Created `app/domain/scraper.py` with four pure functions:
  - `parse_remote_datetime`
  - `normalize_route_data`
  - `should_start_collection`
  - `should_stop_collection`
- `scraper_async.py` imports them from domain; `_should_start/stop_collection` methods become one-line delegates
- Updated `test_scraper_async.py`: imports and datetime patches retargeted to `app.domain.scraper`

### `test(domain)` → `feat(domain)` → `feat(adapters)` → `refactor(scraper)` — IRouteDataRepository port

- Created `app/domain/ports.py` with `IRouteDataRepository` ABC (4 methods):
  - `create_task(start_time) -> int`
  - `update_task_status(task_id, status, update_time, stop_time=None)`
  - `save_route_entry(normalized_data)`
  - `update_task_datapoints(task_id, count)`
- Created `app/adapters/route_repository.py` with `SqlAlchemyRouteRepository`
  - accepts injectable `get_session` callable for test isolation
- `AsyncCollectionManager.__init__` now accepts `repository: IRouteDataRepository | None`
  - defaults to `SqlAlchemyRouteRepository()` via lazy import
  - zero SQLAlchemy calls remain in `scraper_async.py`
- Updated `conftest.py`:
  - `clean_collection_manager` — injects `MagicMock(spec=IRouteDataRepository)`
  - new `collection_manager_with_db` — injects real repo with test session (for DB-asserting tests)
- Updated `test_scraper_async.py`:
  - two integration tests now use `collection_manager_with_db`
  - DB error test replaced `patch("app.scraper_async.RouteDataEntry")` with mock `side_effect`
- Also moved `get_db_session` from `scraper_async.py` to `app/database.py`

### `test(domain)` → `feat(domain)` → `feat(adapters)` → `refactor(scraper)` — ICollectionStateStore port

- Extended `app/domain/ports.py` with `CollectionSnapshot` dataclass and `ICollectionStateStore` ABC:
  - `CollectionSnapshot` — immutable view: `task_id`, `status`, `start_time`, `stop_time`, `datapoints_collected`
  - `initialize(task_id, start_time)` — resets all state for a new run
  - `set_status(status, stop_time=None)` — updates status; preserves existing `stop_time` if none given
  - `increment_datapoints() -> int` — increments counter, returns new value
  - `check_and_update_hash(data_hash) -> bool` — deduplication; returns True if hash differs; resets on `initialize`
  - `get_snapshot() -> CollectionSnapshot` — point-in-time read
- Created `app/adapters/collection_state.py` with `InMemoryCollectionState`
- `AsyncCollectionManager` state fields (`_status`, `current_task_id`, `datapoints_collected`, `start_time`, `stop_time`) are now read-only properties delegating to `_state.get_snapshot()`; `_status` also has a setter (for `patch.object`/`PropertyMock` compatibility in API tests)
- `last_data_hash` removed from manager; `_check_data_changed` delegates to `_state.check_and_update_hash`
- `conftest.py` fixtures (`clean_collection_manager`, `collection_manager_with_db`) updated: manual field resets replaced by injecting a fresh `InMemoryCollectionState()`
- `test_api_endpoints.py`: `patch('...._status', value)` updated to `patch.object(AsyncCollectionManager, '_status', new_callable=PropertyMock)` — required because Python 3.12 mock tries `delattr` (not `setattr`) when the attribute is not in the instance `__dict__`

---

## Final state after this session

| File                                 | Role                                                  |
| ------------------------------------ | ----------------------------------------------------- |
| `app/main.py`                        | FastAPI routes + lifespan wiring                      |
| `app/scheduler.py`                   | `Scheduler` class                                     |
| `app/scraper_async.py`               | HTTP/session management only                          |
| `app/domain/scraper.py`              | Pure business logic (no I/O)                          |
| `app/domain/ports.py`                | `IRouteDataRepository` + `ICollectionStateStore` ABCs |
| `app/adapters/route_repository.py`   | SQLAlchemy implementation                             |
| `app/adapters/collection_state.py`   | In-memory state store                                 |
| `app/cookie_refresh/`                | Already Clean Arch — untouched                        |

**Test results:** 268 tests, 97% coverage, all green.

---

## Dependency rule (enforced)

```text
infrastructure → adapters → application → domain
```

`scraper_async.py` (application) depends on `domain/ports.py` only.
`adapters/route_repository.py` depends on `models.py` and `database.py`.
`adapters/collection_state.py` depends on `domain/ports.py` and `models.py` only.

---

---

# vtrack — Layer 3 OTel observability session 2026-05-19

## Goal

Add distributed tracing across every service in the stack so any anomaly — missed slot,
slow collection, failed alert delivery — is visible in Grafana without digging through logs.

---

## Scope

Extended beyond the original Layer 3 spec (conductor + vtrack only) to include:
- `alert-processor` microservice
- `notification-sender` microservice
- `cookie_refresh` module inside vtrack

---

## Span hierarchy as implemented

```text
[conductor]
  conductor.slot                    {slot.name, slot.date}
    ├── conductor.container.start   {containers.count}
    ├── conductor.health.wait
    ├── conductor.guardian.activate {slot.name}    ← traceparent injected via httpx
    ├── conductor.resource.eval     {resource.total_memory_mb, resource.total_cpu_percent, resource.decision}
    └── conductor.slot.watch        {slot.outcome}

[vtrack — continued from traceparent header]
  guardian.slot.{name}              {slot.name}
    ├── guardian.watching
    └── guardian.collection.start   {trigger}
          collection.run            {collection.task_id, collection.datapoints, collection.duration_s}
            └── cookie_refresh.run  {refresh.success, refresh.steps_taken}

[alert-processor — independent root spans]
  alert_processor.coordinate.process  {coordinate.ruta, coordinate.latitude,
                                        coordinate.longitude, alerts.generated}
    └── alert_processor.alert.queue   {alert.type, alert.zone}

[notification-sender — independent root spans]
  notification_sender.alert.send      {alert.ruta, alert.type,
                                        notification.provider, notification.success}
```

---

## Trace topology decisions

- `conductor → vtrack` linked via W3C `traceparent` HTTP header (httpx auto-injects via `AsyncOpenTelemetryTransport`; FastAPI auto-extracts via `opentelemetry-instrumentation-fastapi`)
- `alert-processor` and `notification-sender` emit independent root spans — correlated in Grafana by matching `slot.date`/`slot.name` attributes. Avoids modifying the shared Redis message schema.
- `alert.severity` omitted from all span attributes — field is scheduled for deprecation.
- `collection.run` span uses `tracer.start_span()` (not context manager) since it spans `start()` → `stop()` method boundaries on `AsyncCollectionManager`.

---

## Architecture rule (upheld)

| Layer | OTel code allowed |
|---|---|
| `domain/` | none |
| `application/` (conductor.py, scheduler.py, scraper_async.py, AlertConsumer, NotificationConsumer) | `from opentelemetry import trace` — API only |
| `adapters/tracing.py` | SDK + OTLP exporter — `configure_tracing()` only |
| `infrastructure/main.py` | calls `configure_tracing(service_name, endpoint)` |

---

## Files created / modified

| File | Change |
|---|---|
| `microservices/conductor/adapters/tracing.py` | new — `configure_tracing()` |
| `app/tracing.py` | new — `configure_tracing()` |
| `microservices/alert-processor/tracing.py` | new — `configure_tracing()` |
| `microservices/notification-sender/tracing.py` | new — `configure_tracing()` |
| `microservices/conductor/conductor.py` | instrumented with 5 child spans |
| `microservices/conductor/adapters/vtrack_gateway.py` | added optional `transport` param |
| `microservices/conductor/main.py` | wires `configure_tracing` + `AsyncOpenTelemetryTransport` |
| `microservices/conductor/requirements.txt` | +4 OTel packages |
| `app/scheduler.py` | instrumented with `guardian.slot.*` spans |
| `app/scraper_async.py` | instrumented with `collection.run` span |
| `app/cookie_refresh/__init__.py` | instrumented with `cookie_refresh.run` span |
| `app/main.py` | wires `configure_tracing` in lifespan |
| `app/tests/conftest.py` | added shared session-scoped OTel fixtures |
| `requirements.txt` | +4 OTel packages for vtrack |
| `microservices/alert-processor/main.py` | instrumented + `configure_tracing` wired; extracted clean span structure |
| `microservices/alert-processor/requirements.txt` | +3 OTel packages |
| `microservices/notification-sender/main.py` | extracted `_process_alert_queue()`; instrumented + `configure_tracing` wired |
| `docker-compose.yml` | added tempo, prometheus, grafana services; `OTLP_ENDPOINT` on all 4 services |
| `docker/tempo/tempo.yaml` | new — Tempo OTLP receiver + local storage config |
| `docker/prometheus/prometheus.yml` | new — scrapes vtrack `/metrics` |
| `docker/grafana/provisioning/datasources/datasources.yaml` | new — Tempo + Prometheus datasources |

---

## Test suites added

| File | Tests |
|---|---|
| `microservices/conductor/tests/test_conductor_otel.py` | conductor span creation and attributes |
| `microservices/conductor/tests/test_trace_propagation.py` | traceparent header injection via httpx |
| `app/tests/test_guardian_otel.py` | guardian slot + watching + collection.start spans |
| `app/tests/test_collection_otel.py` | collection.run span with task_id / datapoints / duration |
| `app/tests/test_cookie_refresh_otel.py` | cookie_refresh.run span, success + failure cases |
| `microservices/alert-processor/tests/test_alert_processor_otel.py` | coordinate.process + alert.queue spans |
| `microservices/notification-sender/tests/test_notification_sender_otel.py` | alert.send span, provider + success attrs |

---

## Notable implementation details

- **OTel global singleton reset in tests**: `trace_api._TRACER_PROVIDER_SET_ONCE._done = False` required in Python 3.12 — the internal guard uses a `Once` object, not a simple boolean flag.
- **Session-scoped provider in conftest.py**: `app/tests/conftest.py` holds a single session-scoped `InMemorySpanExporter` shared across all vtrack OTel test files. Module-level `_tracer = trace.get_tracer(__name__)` caches the real tracer on first resolution; multiple session fixtures each resetting the global provider caused cross-file test failures.
- **`StopIteration` in async tests**: `next(generator)` inside `async def` raises `RuntimeError` in Python 3.12. Fixed by using `next(gen, None)` throughout OTel test assertions.
- **`AsyncOpenTelemetryTransport`**: Used as per-client transport wrapper on `HttpxVtrackGateway` (not `HTTPXClientInstrumentor.instrument()`). Injected via optional `transport` constructor param for testability.

---

## Commit sequence (19 commits)

```
test(conductor): add failing otel span tests
feat(conductor): instrument conductor with otel spans
test(conductor): add failing trace propagation tests
feat(conductor): add transport param to gateway
test(scheduler): add failing guardian otel span tests
feat(scheduler): instrument guardian with otel child spans
test(scraper): add failing collection.run otel span tests
feat(scraper): instrument collection run with otel span
test(cookies): add failing cookie_refresh.run otel span tests
feat(cookies): instrument cookie_refresh.run with otel span
chore(infra): add tracing.py to all four services
chore(infra): wire otel sdk in main.py for conductor and vtrack
test(alerts): failing tests for otel spans in alert consumer
feat(alerts): instrument alert-processor with otel spans
chore(infra): wire otel sdk in alert-processor main
test(alerts): red otel spans for notification-sender
feat(alerts): instrument notification-sender with otel spans
chore(infra): wire otel sdk in notification-sender main
chore(infra): add tempo, prometheus, grafana to docker-compose
```

---

## Final test count

| Suite | Tests |
|---|---|
| vtrack (`app/tests/`) | 354 |
| alert-processor | 5 |
| notification-sender (OTel) | 6 |
| conductor | 62 |
| **Total** | **427** |

All green.
