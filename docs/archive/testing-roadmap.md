# 🧪 VTRACK Testing Roadmap

## 📋 Testing Philosophy

**Priority Order:**
1. **Models** (Foundation Layer) - Data validation & constraints
2. **Business Logic** (Service Layer) - Scraper functionality
3. **API Layer** (Interface Layer) - Endpoints & integration

**AAA Pattern (Arrange-Act-Assert):**
- **Arrange**: Set up test data and mocks
- **Act**: Execute the function/endpoint being tested
- **Assert**: Verify the expected outcome

---

## 🎯 TASK 2: Testing Roadmap

### Phase 1: Model Testing (Priority: HIGH)

**File:** `test_models.py`

**Why test models first?**
- Models are the foundation of your application
- If data validation fails, everything downstream breaks
- Catching validation errors early prevents production bugs
- Database constraints ensure data integrity

**What we test:**

#### 1.1 Pydantic Schema Validation
- ✅ Valid data passes validation
- ✅ Invalid data types raise ValidationError
- ✅ Required fields are enforced
- ✅ Optional fields handle None correctly
- ✅ Custom validators work as expected
- ✅ DateTime handling with timezone awareness

**Example Test Cases:**
```python
# ScrapingResponse validation
- Valid valores_data and estados_data
- Empty lists are handled
- Nested list structures are validated

# CollectionStatusResponse validation
- All enum values are accepted
- Optional fields can be None
- DateTime fields are timezone-aware
```

#### 1.2 SQLAlchemy Model Testing
- ✅ Models can be created and saved
- ✅ Primary keys auto-increment
- ✅ Foreign key constraints work
- ✅ Nullable/non-nullable fields enforced
- ✅ Default values are set correctly
- ✅ Timestamps are timezone-aware

**Example Test Cases:**
```python
# RouteDataEntry model
- Creating entry with valid data succeeds
- Missing required field raises error
- Latitude/longitude accept floats
- Timestamps are nullable where allowed
- collected_at has automatic default

# CollectionMetadata model
- Session tracking works correctly
- Status field stores enum values
- Datapoints count increments properly
```

---

### Phase 2: Scraper Logic Testing (Priority: HIGH)

**File:** `test_scraper_async.py`

**Why test the scraper?**
- Core business logic of the application
- Complex async operations are error-prone
- External API failures must be handled gracefully
- Session management is critical for reliability

**What we test:**

#### 2.1 Session Management
- ✅ Login creates valid session
- ✅ Session cookies are stored
- ✅ Expired sessions trigger re-login
- ✅ Valid sessions are reused
- ✅ Session cleanup on stop

**Testing Challenge:** The scraper runs in a while loop
**Solution:** Mock the external API and control the loop iteration count

#### 2.2 Data Fetching
- ✅ Successful data fetch returns ScrapingResponse
- ✅ HTTP errors trigger retry logic
- ✅ Invalid JSON is handled gracefully
- ✅ Network timeouts don't crash the app

#### 2.3 Data Normalization
- ✅ Valid data is normalized correctly
- ✅ Invalid date formats (0000-00-00) return None
- ✅ Missing fields are handled
- ✅ Type conversion errors are caught

#### 2.4 Collection State Machine
- ✅ IDLE → ONGOING when route starts
- ✅ ONGOING → FINISHED when route completes
- ✅ Data is saved only when changed
- ✅ Start/stop conditions work correctly

**Key Pattern for Testing While Loops:**
```python
# Mock the external fetch to return different data on each call
async def mock_fetch_with_sequence():
    call_count = 0
    async def _fetch():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {"status": "En recorrido"}  # Start collection
        elif call_count == 2:
            return {"status": "En recorrido"}  # Continue
        else:
            return {"status": "Completed"}  # Stop condition
    return _fetch
```

#### 2.5 AsyncCollectionManager Lifecycle
- ✅ start() initializes metadata
- ✅ stop() cancels running task
- ✅ Cannot start if already running
- ✅ get_status() returns accurate info
- ✅ Datapoints are counted correctly

---

### Phase 3: API Integration Testing (Priority: MEDIUM)

**File:** `test_api_endpoints.py` & `test_data_server.py`

**Why test endpoints last?**
- Depends on models and business logic working
- Integration tests verify the full stack
- API contracts must be stable for clients

**What we test:**

#### 3.1 Collection Control Endpoints (main.py)

**POST /collect/start**
- ✅ Starts collection when idle
- ✅ Returns 400 if already running
- ✅ Returns CollectionStatusResponse
- ✅ Initializes metadata in database

**POST /collect/stop**
- ✅ Stops running collection
- ✅ Returns 400 if not running
- ✅ Updates metadata with stop_time

**GET /collect/status**
- ✅ Returns current status
- ✅ Includes scheduler information
- ✅ Shows datapoints collected

**POST /fetch-remote-data**
- ✅ Fetches data from external API (mocked)
- ✅ Returns ScrapingResponse
- ✅ Handles scraper errors gracefully

#### 3.2 Scheduler Endpoints (main.py)

**POST /scheduler/start**
- ✅ Starts the scheduler
- ✅ Returns success message

**POST /scheduler/stop**
- ✅ Stops the scheduler
- ✅ Cancels scheduled tasks

**GET /scheduler/status**
- ✅ Returns scheduler state
- ✅ Shows next run times

#### 3.3 Data Server Endpoints (data_server.py)

**GET /data/sessions/{session_id}/datapoints**
- ✅ Returns collection and its datapoints
- ✅ Returns 404 for invalid session_id
- ✅ Handles null stop_time (ongoing)
- ✅ Filters datapoints by time range

**POST /data/datapoints/range**
- ✅ Returns datapoints in time range
- ✅ Returns 400 if start > stop
- ✅ Returns empty list for no matches
- ✅ Handles timezone-aware datetimes

---

## 🧰 Testing Tools & Utilities

### Required Dependencies
```txt
pytest>=8.0.0
pytest-asyncio>=0.23.0
httpx>=0.28.0
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest app/tests/test_models.py

# Run specific test
pytest app/tests/test_models.py::test_route_data_entry_creation

# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run with verbose output
pytest -v

# Run tests in parallel (after installing pytest-xdist)
pytest -n auto
```

---

## 📊 Test Coverage Goals

| Component | Coverage Target | Why |
|-----------|----------------|-----|
| models.py | 100% | Simple validation logic |
| scraper_async.py | 90%+ | Core business logic |
| main.py | 85%+ | Some paths are scheduler-dependent |
| data_server.py | 100% | Simple CRUD operations |
| database.py | 70%+ | Mostly configuration |

---

## 🎓 Senior Dev Tips

### 1. Test Isolation is Sacred
- Each test should be independent
- Use transactions and rollbacks
- Never rely on test execution order

### 2. Mock at the I/O Boundary
- Mock HTTP calls, not business logic
- This tests YOUR code, not external APIs
- Keep mocks simple and realistic

### 3. Test Behavior, Not Implementation
- Don't test private methods directly
- Test public interfaces and outcomes
- Refactoring shouldn't break tests

### 4. Descriptive Test Names
```python
# ❌ Bad
def test_scraper():

# ✅ Good
def test_scraper_starts_collection_when_route_status_is_en_recorrido():
```

### 5. Fast Tests are Good Tests
- Use in-memory SQLite (not PostgreSQL)
- Mock external API calls
- Avoid unnecessary sleeps
- Target: <5 seconds for entire suite

---

## 🐛 Common Testing Pitfalls

### Pitfall 1: Not Cleaning Up Async Tasks
```python
# ❌ Bad - leaves tasks running
await manager.start()
# test ends, task still running

# ✅ Good - proper cleanup
await manager.start()
try:
    # test code
finally:
    await manager.stop()
```

### Pitfall 2: Timezone-Naive Datetimes
```python
# ❌ Bad - no timezone
datetime.now()

# ✅ Good - timezone aware
datetime.now(ZoneInfo("America/Bogota"))
```

### Pitfall 3: Testing Implementation Details
```python
# ❌ Bad - tests internal state
assert manager._lock.locked()

# ✅ Good - tests behavior
assert manager._is_running == True
```

---

## 📈 Next Steps After Testing Suite

1. **Set up CI/CD** - Run tests on every commit
2. **Add coverage reporting** - Track coverage over time
3. **Performance testing** - How many requests/second can you handle?
4. **Load testing** - What happens with 1000 concurrent users?
5. **End-to-end testing** - Test with real browser (Playwright/Selenium)

---

## 🎯 Success Criteria

Your test suite is production-ready when:

- ✅ All tests pass consistently
- ✅ Tests run in under 10 seconds
- ✅ Coverage is above 85%
- ✅ No flaky tests (random failures)
- ✅ Tests document how the system works
- ✅ Developers trust the tests
- ✅ Refactoring is safe and easy

---

**Remember:** Good tests are your safety net. Write them like your production system depends on it... because it does! 🚀
