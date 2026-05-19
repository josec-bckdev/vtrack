# Conductor

Lightweight always-on microservice that owns the vtrack container lifecycle.  
It is the **sole service with `restart: always`** — every other managed container is started and stopped by the conductor around collection windows.

---

## What it does

```
Host boot
  └── Docker daemon (systemd) starts conductor
        │
        ├── Boot sequence
        │     ├─ Outside window? → stop any running managed containers
        │     └─ Inside window?  → start stack, wait for health, activate guardian
        │
        └── Main loop (repeats forever)
              ├─ Sleep until next window_open
              ├─ Start all managed containers
              ├─ Wait for GET /monitor/health → 200
              ├─ POST /monitor/guardian/activate?slot=<slot>
              ├─ Query Docker stats for each container
              ├─ Log: "Stopping containers would free X MB / Y% CPU"
              ├─ Watch guardian until task_running = false
              └─ If total_memory ≥ threshold → stop all managed containers
```

---

## Architecture

Follows Clean Architecture — same pattern as `cookie-refresher`.

```
conductor/
  domain/
    ports.py            # IVtrackGateway, IContainerGateway, ContainerStats (pure ABCs)
    resource_policy.py  # evaluate_savings(), should_stop_after_slot() (pure functions)
  adapters/
    vtrack_gateway.py   # HttpxVtrackGateway — thin httpx wrapper
    container_gateway.py # DockerContainerGateway — docker SDK via run_in_executor
  conductor.py          # Conductor class: boot, _startup_slot, _watch_slot, run
  main.py               # Entry point: reads env vars, wires deps, asyncio.run
```

Dependency rule: `conductor.py` → ports (domain), never imports from `app/`.

---

## Managed containers

The conductor starts and stops these containers around each collection window:

| Container | docker-compose name | restart policy |
|---|---|---|
| FastAPI app | `fastapi_api` | `"no"` — conductor owned |
| PostgreSQL | `postgres_db` | `"no"` — conductor owned |
| Redis | `redis_queue` | `"no"` — conductor owned |
| Alert processor | `alert_processor` | `"no"` — conductor owned |
| Notification sender | `notification_sender` | `"no"` — conductor owned |
| **Conductor** | `conductor` | `always` — always on |
| pgadmin | `pgadmin` | `always` — unmanaged admin tool |

---

## Configuration (env vars)

| Variable | Default | Description |
|---|---|---|
| `VTRACK_BASE_URL` | `http://api:8000` | vtrack API base URL |
| `MANAGED_CONTAINERS` | `fastapi_api,postgres_db,redis_queue,alert_processor,notification_sender` | Comma-separated Docker container names |
| `SLOT_MORNING_WINDOW_OPEN` | `05:00` | Morning window opens |
| `SLOT_MORNING_WINDOW_CLOSE` | `06:40` | Morning window closes |
| `SLOT_AFTERNOON_WINDOW_OPEN` | `14:30` | Afternoon window opens |
| `SLOT_AFTERNOON_WINDOW_CLOSE` | `16:30` | Afternoon window closes |
| `MEMORY_THRESHOLD_MB` | `256` | Stop containers after slot if freed memory ≥ this value |
| `TZ` | `America/Bogota` | Timezone for window calculations |

---

## Resource policy

At each `window_open`, the conductor queries Docker stats for every managed container and computes:

- `total_memory_mb` = sum of each container's `memory_stats.usage`
- `total_cpu_percent` = sum of each container's CPU delta ratio × online CPUs × 100

Logs:
```
Resource snapshot: 412 MB / 18.3% CPU across 5 containers
Stopping containers after slot would free 412 MB — decision: STOP
```

If `total_memory_mb ≥ MEMORY_THRESHOLD_MB` → containers are stopped after the slot closes.  
If below threshold → containers are kept running until the next window check.

---

## Deployment

### First-time setup on a new host

```bash
# Ensure Docker starts on boot (usually already enabled)
sudo systemctl enable docker

# Create all containers (without starting them)
docker compose up --no-start

# Start only the conductor — it manages the rest
docker compose up -d conductor
```

### Verify conductor is running

```bash
docker logs conductor -f
# Expected: "Conductor starting", "Boot outside collection windows", "Sleeping Xs until morning window opens"
```

---

## Running tests

```bash
# From the project root
cd microservices/conductor
python -m pytest tests/ -v --cov=. --cov-report=term-missing
```

47 tests, all passing, under 1 second.

---

## Relation to other layers

| Layer | Component | Role |
|---|---|---|
| Layer 1 | Guardian (`app/scheduler.py`) | State machine inside vtrack — ensures collection fires within window |
| **Layer 2** | **Conductor** (this service) | Outside vtrack — owns container lifecycle, activates guardian after boot |
| Layer 3 | OpenTelemetry (planned) | One trace per slot: conductor → guardian → collection |

The conductor never imports from `app/`. It communicates with vtrack exclusively through `IVtrackGateway` → `GET/POST /monitor/*`.
