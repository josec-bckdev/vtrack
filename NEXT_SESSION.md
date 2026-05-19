# vtrack — next session

## Current state (as of 2026-05-19)

The app now follows Clean Architecture throughout:

| Layer         | Module                                         |
| ------------- | ---------------------------------------------- |
| Domain        | `app/domain/scraper.py`, `app/domain/ports.py` |
| Adapters      | `app/adapters/route_repository.py`             |
| Application   | `app/scraper_async.py`, `app/scheduler.py`     |
| Infra/wiring  | `app/main.py`                                  |

244 tests, 97% coverage, all green.

---

## Potential next steps

Pick up any of these in priority order:

**1. Async SQLAlchemy (optional upgrade)**
`SqlAlchemyRouteRepository` uses the sync ORM. If the app moves to async DB (e.g. `asyncpg` + `SQLAlchemy 2 async`), only `adapters/route_repository.py` needs to change — the port interface stays the same.

**2. Integration tests for the full collection loop**
`_collection_loop` is listed in `CLAUDE.md` as a known coverage gap (needs fake httpx over time). Now that DB writes are behind a port, the loop can be tested with a mock repository + mock httpx client without any real infrastructure.

**3. Extract `ICollectionStatePort` (optional)**
`AsyncCollectionManager` still holds in-process state (`_status`, `datapoints_collected`, etc.). If the app needs to scale across processes, this state could be extracted behind a port (e.g. backed by Redis).

**4. Move `get_db_session` out of `scraper_async.py`**
`get_db_session` lives in `scraper_async.py` only as a default for `SqlAlchemyRouteRepository`. It belongs in `app/database.py` next to `SessionLocal`. Small housekeeping move.

---

## Start by reading

`app/scraper_async.py`, `app/adapters/route_repository.py`, `app/domain/ports.py`, `CLAUDE.md`
