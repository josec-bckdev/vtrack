# vtrack — next session

## Current state (as of 2026-05-20)

### Layer summary

| Layer | Status |
| --- | --- |
| Layer 1 — Guardian state machine | complete |
| Layer 2 — Conductor container lifecycle | complete |
| Layer 3 — OpenTelemetry distributed tracing | complete |
| Layer 3 follow-on — Prometheus custom metrics | complete |

**Test count:** 465 tests, all green
- `app/tests/` — 368
- `microservices/conductor/tests/` — 64
- `microservices/notification-sender/tests/` — 33

Single command: `python -m pytest app/tests/ microservices/`

### Services

| Service | Location | OTel spans | Prometheus metrics |
| --- | --- | --- | --- |
| vtrack (FastAPI) | `app/` | guardian.slot.*, collection.run, cookie_refresh.run | HTTP baseline + 3 custom |
| conductor | `microservices/conductor/` | conductor.slot, .container.start, .health.wait, .guardian.activate, .resource.eval, .slot.watch | — |
| alert-processor | `microservices/alert-processor/` | alert_processor.coordinate.process, alert_processor.alert.queue | — |
| notification-sender | `microservices/notification-sender/` | notification_sender.alert.send | — |

### Custom metrics

```
vtrack_collection_total{slot, outcome}     # counter — incremented at end of each guardian run
vtrack_guardian_state{slot, state}         # gauge  — current FSM state per slot
vtrack_collection_datapoints{slot}         # histogram — datapoints collected per run
```

### Observability stack (docker-compose)

- **Tempo** — OTLP gRPC receiver (port 4317), trace storage, HTTP API (port 3200)
- **Prometheus** — scrapes vtrack `/metrics` every 15 s (port 9090)
- **Grafana** — Tempo + Prometheus datasources pre-provisioned (port 3000)

---

## Pending next steps

### 1. Grafana dashboard panels

Spec lives in `GRAFANA_PANELS.md`. Build the four-row dashboard and provision it as code.

**Setup (one-time)**
- Create `docker/grafana/provisioning/dashboards/`
- Add `dashboards.yaml` provider pointing to `/etc/grafana/provisioning/dashboards`
- Mount the directory in `docker-compose.yml` grafana volumes

**Dashboard rows to build**

| Row | Panels |
| --- | --- |
| Collection outcomes | Rate by outcome (time series) · Missed slot count last 7d (stat) |
| Guardian state | State timeline — morning · State timeline — afternoon |
| Datapoints | Per-run histogram (heatmap) · Average per run (stat) |
| HTTP baseline | Request rate · p95 latency · Error rate |

**Checklist**
- [ ] Create provisioning directory structure
- [ ] Build panels in Grafana UI, export JSON to `docker/grafana/provisioning/dashboards/vtrack.json`
- [ ] Add dashboards entry to Grafana compose volume
- [ ] Rebuild: `docker compose up -d grafana`
- [ ] Verify dashboard loads on fresh start
- [ ] Confirm `vtrack_guardian_state` updates live during a forced window test
- [ ] Confirm `vtrack_collection_datapoints_sum` reflects real datapoint counts

---

### 2. Grafana alert rules — Layer 4

Provision Grafana alert rules from YAML in `docker/grafana/provisioning/alerting/`.
Deliver alerts via the existing `notification-sender` → Telegram channel.

**Alert rules**

| Rule | Condition | Severity |
| --- | --- | --- |
| Missed slot | `vtrack_collection_total{outcome="missed"}` fires 2+ consecutive days | critical |
| Slow collection | `collection.duration_s > 1.5 × 7-day rolling average` | warning |
| Alert delivery failure | `notification.success == false` for 3+ consecutive alerts | warning |

**TDD commit sequence**
```
chore(infra): add grafana alert rules provisioning
test(infra): smoke-test alert rule yaml schema
docs(infra): document grafana alerting setup
```

---

### 3. Cookie refresher — retry + health observability

The `cookie_refresh.run` span captures `refresh.success` and `refresh.steps_taken` but there
is no alerting path if the refresh fails inside a live collection window.

**Two improvements**
- Add a `refresh.error` span event (not a new span) on `result.success == False` in
  `app/cookie_refresh/__init__.py`
- Expose `vtrack_cookie_refresh_last_success_ts` Prometheus gauge (Unix timestamp of last
  successful refresh) so Grafana can alert when the session is at risk of expiring before
  the next window

**TDD commit sequence**
```
test(cookies): failing test for refresh.error span event
feat(cookies): add refresh.error span event on failure
test(infra): failing test for cookie_refresh_last_success_ts gauge
feat(infra): expose cookie refresh last success timestamp as prometheus gauge
```

---

## Start by reading

`app/scheduler.py`, `app/scraper_async.py`, `app/cookie_refresh/__init__.py`,
`app/metrics.py`, `docker-compose.yml`, `docker/grafana/`, `GRAFANA_PANELS.md`, `CLAUDE.md`
