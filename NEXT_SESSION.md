# vtrack — next session

## Current state (as of 2026-05-19)

The app follows Clean Architecture throughout, and the conductor microservice is live.

### vtrack core (`app/`)

| Layer        | Module                                                                          |
| ------------ | ------------------------------------------------------------------------------- |
| Domain       | `app/domain/scraper.py`, `app/domain/ports.py`                                  |
| Adapters     | `app/adapters/{route_repository,collection_state,collection_status_adapter}.py` |
| Application  | `app/scraper_async.py`, `app/scheduler.py`                                      |
| Infra/wiring | `app/main.py`, `app/monitoring.py`                                              |

341 tests, 97% coverage, all green.

### Conductor microservice (`microservices/conductor/`)

| Layer    | Module                                                        |
| -------- | ------------------------------------------------------------- |
| Domain   | `domain/ports.py`, `domain/resource_policy.py`                |
| Adapters | `adapters/vtrack_gateway.py`, `adapters/container_gateway.py` |
| App      | `conductor.py`                                                |
| Infra    | `main.py`, `Dockerfile`, `requirements.txt`                   |

47 tests, all green. See `microservices/conductor/README.md` for full docs.

### Ports in `app/domain/ports.py`

| Port                       | Adapter                         | Purpose                               |
| -------------------------- | ------------------------------- | ------------------------------------- |
| `IRouteDataRepository`     | `SqlAlchemyRouteRepository`     | DB persistence for collection tasks   |
| `ICollectionStateStore`    | `InMemoryCollectionState`       | In-process state (status, counters)   |
| `ICollectionStatusAdapter` | `AsyncCollectionManagerAdapter` | Narrow bridge for guardian → manager  |

### Ports in `microservices/conductor/domain/ports.py`

| Port                | Adapter                   | Purpose                              |
| ------------------- | ------------------------- | ------------------------------------ |
| `IVtrackGateway`    | `HttpxVtrackGateway`      | HTTP calls to vtrack `/monitor/*`    |
| `IContainerGateway` | `DockerContainerGateway`  | Docker lifecycle via docker SDK      |

### Container lifecycle

The conductor (`restart: always`) is the sole always-on process. All five managed
containers (`api`, `db`, `redis`, `alert-processor`, `notification-sender`) have
`restart: "no"` and are started/stopped by the conductor around each collection window.

---

## Layer 1 — Guardian (completed)

`app/scheduler.py` — state machine that watches one slot per day and ensures
collection fires within the window. Per-slot states: `IDLE → WATCHING → STARTED | MISSED`.
Endpoints in `app/monitoring.py`: `GET /monitor/guardian`, `POST /monitor/guardian/activate`.

---

## Layer 2 — Conductor (completed)

`microservices/conductor/conductor.py` — ReAct loop that owns container lifecycle:

1. **Boot sequence** — on startup, check clock. If inside a window: start stack,
   wait for health, activate guardian. If outside: stop any running managed containers.
2. **Slot startup** (`_startup_slot`) — at each `window_open`: start all managed
   containers, wait for `GET /monitor/health` → 200, activate guardian, query Docker
   stats for all containers, compute `ResourceSummary`, log savings estimate, return
   `should_stop_after_slot(summary)`.
3. **Watch slot** (`_watch_slot`) — poll `GET /monitor/guardian` every 30 s until
   `task_running` is False. Log `last_outcome`; warn if `missed`.
4. **Main loop** — sleep until `_next_slot_open()`, run startup + watch, optionally
   stop all containers if resource threshold exceeded.

---

## Layer 3 — OpenTelemetry (next)

One distributed trace per slot per day ties conductor → guardian → collection together.
The conductor creates the root span; vtrack continues it via W3C `traceparent` header.

### Infrastructure stack additions

```text
docker-compose.yml additions:
  tempo        — Grafana Tempo (OTLP receiver + trace storage)
  prometheus   — Prometheus (metrics scrape from vtrack /metrics)
  grafana      — Grafana (dashboards: traces via Tempo, metrics via Prometheus)
```

No OTel collector needed — both services export OTLP directly to Tempo over gRPC (port 4317).

### File changes

**conductor** (new files):

```text
microservices/conductor/
  adapters/
    tracing.py          # configure_tracing(service_name, otlp_endpoint) — SDK setup only
```

**vtrack** (new files):

```text
app/
  tracing.py            # configure_tracing(service_name, otlp_endpoint) — SDK setup only
```

Both `tracing.py` files have the same shape — they configure the SDK and live in
infrastructure only. Application-layer code (`conductor.py`, `scheduler.py`,
`scraper_async.py`) imports only `opentelemetry-api`, which is a no-op when not configured.

### Span hierarchy

```text
[conductor] conductor.slot                {slot: "morning", date: "2026-05-20"}
  ├── conductor.container.start           {containers: [...], count: 5}
  ├── conductor.health.wait               {elapsed_s: 8}
  ├── conductor.guardian.activate         {slot: "morning"}           ← traceparent injected here
  ├── conductor.resource.eval             {total_memory_mb: 412, total_cpu_percent: 18.3, decision: "stop"}
  └── conductor.slot.watch                {outcome: "started", duration_s: 3420}

[vtrack — continued from traceparent header]
  guardian.slot.morning                   {slot: "morning"}
    ├── guardian.watching                 {waited_for_fire: true}
    └── guardian.collection.start         {trigger: "grace_exceeded" | "already_running"}
          collection.run                  {datapoints: 847, duration_s: 3400}
```

### Trace propagation mechanism

1. Conductor creates root span for the slot using `tracer.start_as_current_span(...)`.
2. `HttpxVtrackGateway` is instrumented with `opentelemetry-instrumentation-httpx` —
   it auto-injects the `traceparent` header into every outgoing request.
3. vtrack's FastAPI app uses `opentelemetry-instrumentation-fastapi` — it auto-extracts
   the trace context from incoming requests and makes it the active span context.
4. `app/scheduler.py` calls `tracer.start_as_current_span(...)` inside `_watch_slot`
   and `_run_and_record` — these spans become children of the incoming context.
5. `app/scraper_async.py` wraps `start()` and `_collection_loop()` with a span.

### Where OTel code lives per layer

| Layer | File | What it does |
| --- | --- | --- |
| Infrastructure | `conductor/main.py` | calls `configure_tracing("conductor", ...)` |
| Infrastructure | `app/main.py` | calls `configure_tracing("vtrack", ...)` in lifespan |
| Infrastructure | `conductor/adapters/tracing.py` | `configure_tracing()` — SDK + OTLP exporter setup |
| Infrastructure | `app/tracing.py` | same as above for vtrack |
| Application | `conductor/conductor.py` | `from opentelemetry import trace` — creates slot spans |
| Application | `app/scheduler.py` | creates guardian child spans |
| Application | `app/scraper_async.py` | creates collection span |
| Adapter | `conductor/adapters/vtrack_gateway.py` | httpx auto-instrumentation injects headers |
| Adapter | `app/monitoring.py` / FastAPI | fastapi auto-instrumentation extracts headers |

**Rule:** only `opentelemetry-api` in application/domain layers.
`opentelemetry-sdk` and exporters only in infrastructure (`tracing.py`, `main.py`).

### Key attributes to set on spans

`conductor.slot`:

- `slot.name` = `"morning"` / `"afternoon"`
- `slot.date` = ISO date string
- `slot.outcome` = `"started"` / `"missed"` (set at end of `_watch_slot`)
- `slot.containers_stopped` = `true` / `false`

`collection.run`:

- `collection.datapoints` = final count
- `collection.duration_s` = wall clock seconds
- `collection.task_id` = DB task ID

### Prometheus metrics (optional, same session or follow-on)

Expose via `prometheus-fastapi-instrumentator` on vtrack, scrape with Prometheus:

- `vtrack_collection_total{slot, outcome}` — counter
- `vtrack_collection_datapoints{slot}` — histogram
- `vtrack_guardian_state{slot, state}` — gauge

### TDD commit sequence

1. `test(conductor): failing tests for otel span creation in startup slot`
2. `feat(conductor): instrument conductor with otel spans`
3. `test(conductor): failing tests for trace context propagation in gateway`
4. `feat(conductor): propagate trace context via httpx instrumentation`
5. `test(scheduler): failing tests for guardian otel child spans`
6. `feat(scheduler): instrument guardian with otel child spans`
7. `test(scraper): failing tests for collection otel span`
8. `feat(scraper): instrument collection run with otel span`
9. `chore(infra): add tracing.py to conductor and vtrack`
10. `chore(infra): wire otel sdk in main.py files`
11. `chore(infra): add tempo, prometheus and grafana to docker-compose`

### Testing OTel with InMemorySpanExporter

Tests use `opentelemetry-sdk`'s `InMemorySpanExporter` — no real backend needed:

```python
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

@pytest.fixture
def span_exporter():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    yield exporter
    exporter.clear()

def test_startup_slot_creates_root_span(span_exporter, ...):
    await conductor._startup_slot("morning")
    spans = span_exporter.get_finished_spans()
    names = [s.name for s in spans]
    assert "conductor.slot" in names
    root = next(s for s in spans if s.name == "conductor.slot")
    assert root.attributes["slot.name"] == "morning"
```

### New packages

**conductor `requirements.txt`:**

```text
opentelemetry-api==1.25.0
opentelemetry-sdk==1.25.0
opentelemetry-exporter-otlp-proto-grpc==1.25.0
opentelemetry-instrumentation-httpx==0.46b0
```

**vtrack `requirements.txt`:**

```text
opentelemetry-api==1.25.0
opentelemetry-sdk==1.25.0
opentelemetry-exporter-otlp-proto-grpc==1.25.0
opentelemetry-instrumentation-fastapi==0.46b0
```

### docker-compose additions (sketch)

```yaml
tempo:
  image: grafana/tempo:latest
  container_name: tempo
  restart: always
  command: ["-config.file=/etc/tempo.yaml"]
  volumes:
    - ./docker/tempo/tempo.yaml:/etc/tempo.yaml
    - tempo_data:/var/tempo
  ports:
    - "4317:4317"   # OTLP gRPC
    - "3200:3200"   # Tempo HTTP API (Grafana data source)
  networks:
    - vtrack-network

prometheus:
  image: prom/prometheus:latest
  container_name: prometheus
  restart: always
  volumes:
    - ./docker/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
  ports:
    - "9090:9090"
  networks:
    - vtrack-network

grafana:
  image: grafana/grafana:latest
  container_name: grafana
  restart: always
  environment:
    GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD}
  volumes:
    - grafana_data:/var/lib/grafana
    - ./docker/grafana/provisioning:/etc/grafana/provisioning
  ports:
    - "3000:3000"
  depends_on:
    - tempo
    - prometheus
  networks:
    - vtrack-network
```

Conductor and vtrack both set `OTLP_ENDPOINT=http://tempo:4317` via env var.

---

## Layer 4 — Alerting (follow-on)

Grafana alert rules on top of Prometheus metrics:

- Alert if `slot.outcome == "missed"` for 2 consecutive days
- Alert if `collection.duration_s` exceeds 1.5× the rolling average
- Delivered via existing `notification-sender` (Telegram)

---

## Start by reading

`microservices/conductor/conductor.py`, `app/scheduler.py`, `app/scraper_async.py`,
`app/monitoring.py`, `app/main.py`, `microservices/conductor/README.md`, `CLAUDE.md`
