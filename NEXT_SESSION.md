# vtrack — next session

## Current state (as of 2026-05-19)

### Layer summary

| Layer | Status |
| --- | --- |
| Layer 1 — Guardian state machine | complete |
| Layer 2 — Conductor container lifecycle | complete |
| Layer 3 — OpenTelemetry distributed tracing | complete |

**Test count:** 427 tests, all green (354 vtrack · 62 conductor · 5 alert-processor · 6 notification-sender OTel)

### Services

| Service | Location | OTel spans |
| --- | --- | --- |
| vtrack (FastAPI) | `app/` | guardian.slot.*, collection.run, cookie_refresh.run |
| conductor | `microservices/conductor/` | conductor.slot, .container.start, .health.wait, .guardian.activate, .resource.eval, .slot.watch |
| alert-processor | `microservices/alert-processor/` | alert_processor.coordinate.process, alert_processor.alert.queue |
| notification-sender | `microservices/notification-sender/` | notification_sender.alert.send |

### Observability stack (docker-compose)

- **Tempo** — OTLP gRPC receiver (port 4317), trace storage, HTTP API (port 3200)
- **Prometheus** — scrapes vtrack `/metrics` (port 9090)
- **Grafana** — dashboards with Tempo + Prometheus datasources pre-provisioned (port 3000)

---

## Proposed next steps

### 1. End-to-end smoke test (immediate — no code required)

Bring up the full stack and verify traces flow end-to-end before trusting the instrumentation in production.

```bash
docker-compose up -d
# trigger a collection cycle
curl -X POST http://localhost:8000/collect/start
# open Grafana → Explore → Tempo → Search by service.name=conductor
```

Check:

- `conductor.slot` root span appears with all child spans
- `guardian.slot.*` continues as a child (same trace ID)
- `collection.run` nested under `guardian.collection.start`
- `alert_processor.coordinate.process` appears (independent trace, correlated by `slot.date`)
- `notification_sender.alert.send` appears with `notification.success=true`

---

### 2. Prometheus custom metrics on vtrack (Layer 3 follow-on)

The observability stack already scrapes `/metrics`, but vtrack doesn't expose custom metrics yet.
Add `prometheus-fastapi-instrumentator` for baseline HTTP metrics plus three custom counters/gauges:

```python
# counters / gauges to expose
vtrack_collection_total{slot, outcome}     # counter — incremented at end of each collection run
vtrack_collection_datapoints{slot}         # histogram — datapoints collected per run
vtrack_guardian_state{slot, state}         # gauge — current guardian state (IDLE/WATCHING/STARTED/MISSED)
```

**TDD commit sequence:**

1. `test(infra): failing tests for custom prometheus metrics endpoint`
2. `feat(infra): expose collection metrics via prometheus`
3. `chore(infra): add prometheus-fastapi-instrumentator to requirements`

**New package:** `prometheus-fastapi-instrumentator>=7.0.0`

---

### 3. Grafana alert rules — Layer 4

Grafana alert rules on top of the Prometheus metrics and Tempo data.
Delivers alerts via the existing `notification-sender` → Telegram channel.

**Alert rules to configure (in `docker/grafana/provisioning/alerting/`):**

| Rule | Condition | Severity |
| --- | --- | --- |
| Missed slot | `slot.outcome == "missed"` for 2+ consecutive days | critical |
| Slow collection | `collection.duration_s > 1.5 × 7-day rolling average` | warning |
| Alert delivery failure | `notification.success == false` for 3+ consecutive alerts | warning |

**TDD commit sequence:**

1. `chore(infra): add grafana alert rules provisioning`
2. `test(infra): smoke-test alert rule yaml schema`
3. `docs(infra): document grafana alerting setup`

---

### 4. Deprecate `alert.severity` — side quest

`alert.severity` is stale: it was intentionally omitted from all OTel span attributes this sprint.
Remove it from the domain model and the shared Redis message schema to clean up the field everywhere.

**TDD commit sequence:**

1. `test(domain): failing test for LocationAlert without severity field`
2. `feat(domain): remove severity from LocationAlert and AlertSeverity enum`
3. `refactor(alerts): drop severity from push_alert payload and pop_alert parsing`
4. `refactor(alerts): remove severity from notification-sender message formatting`

**Files to touch:**

- `shared-package/src/shared/location_alerts.py` — remove `AlertSeverity` enum and `severity` field from `LocationAlert`
- `shared-package/src/shared/message_queue.py` — remove `severity` param from `push_alert`, drop from `pop_alert` dict
- `microservices/alert-processor/main.py` — remove `severity=alert.severity.value` from `push_alert` call
- `microservices/notification-sender/providers/telegram.py` — remove severity from message formatting

---

### 5. Pytest collection fix for microservice test suites

Running all microservice tests together from the repo root currently fails with
`ModuleNotFoundError: No module named 'tests.test_alert_processor_otel'` because
each microservice has a `tests/` package and pytest's import mode creates a collision.

**Fix options (pick one):**

- Add `__init__.py` files with unique package names to each microservice `tests/` dir
- Set `pythonpath` in each microservice's `pytest.ini` and use `importmode = importlib`
- Add a root-level `pytest.ini` `testpaths` that excludes microservice roots and run per-service in CI

This is low-risk and makes it possible to run the full repo test suite in one command.

---

### 6. Cookie refresher — retry + health observability

The `cookie_refresh.run` span captures `refresh.success` and `refresh.steps_taken` but there is
no alerting if the refresh fails during a live collection window. Two improvements:

- Add a `refresh.error` span event (not a new span) when `result.success == False`
- Expose a Prometheus gauge `vtrack_cookie_refresh_last_success_ts` (Unix timestamp of last success)
  so Grafana can alert when the session is at risk of expiring before the next window

---

## Start by reading

`app/scheduler.py`, `app/scraper_async.py`, `microservices/conductor/conductor.py`,
`app/monitoring.py`, `docker-compose.yml`, `docker/grafana/`, `CLAUDE.md`
