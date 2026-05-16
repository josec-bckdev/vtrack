# vtrack — AI Development Guidelines

This file configures how Claude Code collaborates on this project.
It encodes the engineering practices that must be maintained across all sessions.

---

## Architecture contract

The project follows **Clean Architecture** within each bounded context. The dependency rule is non-negotiable:

```
infrastructure → adapters → application → domain
```

- `domain/` — pure Python only. No framework imports, no I/O.
- `application/` — imports only from `domain/`. No SDK or framework imports.
- `adapters/` — implements domain ports. May import `httpx`, `fastapi`, `sqlalchemy`.
- `infrastructure/` — wires everything. May import any external library.

Sub-packages that don't warrant full layering (e.g. a single module feature) still obey the spirit of the rule: no circular imports, no business logic in infrastructure.

---

## TDD workflow (non-negotiable)

Follow **red → green → refactor** strictly:

1. **RED** — Write a failing test first. Commit it: `test(scope): add failing test for X`
2. **GREEN** — Write the minimum code to make it pass. Commit: `feat(scope): implement X`
3. **REFACTOR** — Clean up without changing behaviour. Commit: `refactor(scope): simplify X`

Never write implementation code before a test exists for it.
Test the behaviour, not the implementation. Mock only at port boundaries (`IBrowserGateway`, `IVtrackGateway`, etc.).

---

## Commit format (Commitizen)

Format: `type(scope): subject` — lowercase, imperative, no period.

| type | when |
|------|------|
| `feat` | new capability |
| `fix` | bug fix |
| `test` | test-only change |
| `refactor` | restructure without behaviour change |
| `chore` | tooling, deps, CI, config |
| `docs` | documentation only |

Valid scopes: `api`, `domain`, `adapters`, `infra`, `scraper`, `db`, `scheduler`, `cookies`, `alerts`, `queue`, `config`.

Examples:
```
feat(cookies): add no-agent programmed login flow
test(domain): add failing tests for SessionCookies validation
fix(scraper): handle expired session before each collection cycle
chore(config): add vnc-browser on-demand profile to docker-compose
```

---

## Atomic commits with TDD

Every commit must be atomic — one logical change, passing tests, minimal and self-contained. Use this rhythm:

1. **Write failing tests** (RED) → commit with `test(scope): ...`
2. **Implement minimum code to pass** (GREEN) → commit with `feat(scope): ...` or `fix(scope): ...`
3. **Refactor** (REFACTOR) → commit with `refactor(scope): ...` (only if needed)

**Multi-layer changes:** When a feature spans multiple layers, create separate commits per layer:
- Commit 1: `test(domain): add failing tests for X`
- Commit 2: `feat(domain): implement X`
- Commit 3: `test(adapters): add failing tests for Y` (depends on X)
- Commit 4: `feat(adapters): integrate X in adapter layer`

Each commit must:
- Pass all tests
- Be independently understandable
- Have a scope narrower than "multiple unrelated things"

---

## SOLID reminders

- **S** — Each class has one reason to change. `ActionDispatcher` dispatches only. Use cases orchestrate only.
- **O** — Extend behaviour through new implementations of a port, not by editing existing classes.
- **L** — Any mock of `IBrowserGateway` must be a valid substitute for the real implementation.
- **I** — Keep port interfaces narrow. Don't add methods that not all implementations need.
- **D** — Use cases receive ports via constructor injection. Never instantiate gateways inside a use case.

---

## Running tests

```bash
pytest app/tests/ -v --cov=app --cov-report=term-missing
```

Expected output: all tests pass, coverage ≥ 80%.

For a specific sub-package:
```bash
pytest app/tests/cookie_refresh/ -v
```

---

## Known coverage gaps (future integration tests)

These paths require real infrastructure (Docker, running containers, fake clocks)
and are deliberately excluded from the unit test suite. Add integration tests when
the CI environment supports them.

- `cookie_refresh/__init__.py` — `run_refresh()` wiring (needs Docker + VNC container)
- `main.py` — scheduler loop bodies and `/session/refresh` endpoint (needs asyncio fake clock)
- `scraper_async.py` — `_collection_loop` and mid-flight session expiry (needs fake httpx over time)
- `adapters/vnc_browser.py` — stale-network removal path (needs Docker daemon + real container)

---

## What NOT to do

- Do not hardcode credentials anywhere in source files.
- Do not write tests that only verify mock call counts without asserting outcome.
- Do not suppress exceptions silently — log and propagate or convert to domain errors.
- Do not import `docker` or `httpx` inside `domain/` or `application/` layers.
- Do not add a method to a port interface without a corresponding test for it.
- Do not commit implementation without a test commit preceding it.
