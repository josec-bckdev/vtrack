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

---

## Final state after this session

| File                               | Role                             |
| ---------------------------------- | -------------------------------- |
| `app/main.py`                      | FastAPI routes + lifespan wiring |
| `app/scheduler.py`                 | `Scheduler` class                |
| `app/scraper_async.py`             | HTTP/session management only     |
| `app/domain/scraper.py`            | Pure business logic (no I/O)     |
| `app/domain/ports.py`              | `IRouteDataRepository` ABC       |
| `app/adapters/route_repository.py` | SQLAlchemy implementation        |
| `app/cookie_refresh/`              | Already Clean Arch — untouched   |

**Test results:** 244 tests, 97% coverage, all green.

---

## Dependency rule (enforced)

```text
infrastructure → adapters → application → domain
```

`scraper_async.py` (application) depends on `domain/ports.py` only.
`adapters/route_repository.py` depends on `models.py` and `database.py`.
