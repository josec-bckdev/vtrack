# 🧪 VTRACK Testing Suite - Complete Guide

## 📋 Table of Contents
1. [Quick Start](#quick-start)
2. [Testing Infrastructure](#testing-infrastructure)
3. [Running Tests](#running-tests)
4. [Understanding Test Coverage](#understanding-test-coverage)
5. [Writing New Tests](#writing-new-tests)
6. [Troubleshooting](#troubleshooting)

---

## 🚀 Quick Start

### Install Testing Dependencies

```bash
# Make sure you're in the project root
cd /home/bu/PythonCode/vtrack

# Install all dependencies (including test dependencies)
pip install -r requirements.txt
```

### Run All Tests

```bash
# Run the entire test suite
pytest

# Run with verbose output
pytest -v

# Run with coverage report
pytest --cov=app --cov-report=html
```

### Expected Output

```
==================== test session starts ====================
platform linux -- Python 3.12.x
plugins: asyncio-0.23.x, cov-4.1.x
collected 45 items

app/tests/test_models.py ...................... [ 44%]
app/tests/test_scraper_async.py ............... [ 73%]
app/tests/test_api_endpoints.py ............... [100%]

==================== 45 passed in 5.23s ====================
```

---

## 🏗️ Testing Infrastructure

### File Structure

```
vtrack/
├── app/
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py              # ⭐ Fixtures and configuration
│   │   ├── test_models.py           # Unit tests for models
│   │   ├── test_scraper_async.py    # Unit tests for scraper logic
│   │   └── test_api_endpoints.py    # Integration tests for API
├── pytest.ini                        # Pytest configuration
├── requirements.txt                  # Dependencies (including test deps)
├── TESTING_ROADMAP.md               # Strategic testing plan
└── TESTING_GUIDE.md                 # This file!
```

### Key Components

#### 1. `conftest.py` - The Foundation
This file provides **fixtures** (reusable test components):

- **Database Fixtures**
  - `test_engine`: SQLite in-memory engine
  - `db_session`: Clean database session for each test
  - `override_get_db`: Overrides FastAPI dependency

- **HTTP Client Fixtures**
  - `test_client`: Synchronous FastAPI test client
  - `async_test_client`: Async FastAPI test client

- **Mock Fixtures**
  - `mock_scraper_credentials`: Mock environment variables
  - `mock_httpx_client`: Mock HTTP client for external APIs
  - `mock_scraping_response`: Mock external API responses

- **Data Fixtures**
  - `sample_route_data`: Sample route data for testing
  - `bogota_time`: Current time in America/Bogota timezone

#### 2. `pytest.ini` - Configuration
Configures pytest behavior:
- Test discovery patterns
- Async mode settings
- Output formatting
- Markers for organizing tests

---

## 🎯 Running Tests

### Basic Commands

```bash
# Run all tests
pytest

# Run specific test file
pytest app/tests/test_models.py

# Run specific test class
pytest app/tests/test_models.py::TestRouteDataEntryModel

# Run specific test function
pytest app/tests/test_models.py::TestRouteDataEntryModel::test_create_route_data_entry_success

# Run tests matching a pattern
pytest -k "session"  # Runs all tests with "session" in the name
```

### Advanced Commands

```bash
# Run with detailed output
pytest -v -s  # -s shows print statements

# Run only failed tests from last run
pytest --lf

# Run until first failure (useful for debugging)
pytest -x

# Run tests in parallel (faster, requires pytest-xdist)
pip install pytest-xdist
pytest -n auto

# Generate HTML coverage report
pytest --cov=app --cov-report=html
# Then open: htmlcov/index.html
```

### Test Markers

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run only async tests
pytest -m asyncio

# Run only geofence/location analyzer tests
PYTHONPATH=/home/bu/PythonCode/vtrack/shared-package/src:$PYTHONPATH pytest -m geofence -v

# Skip slow tests
pytest -m "not slow"
```

---

## 📊 Understanding Test Coverage

### Viewing Coverage

```bash
# Generate coverage report
pytest --cov=app --cov-report=term-missing

# Output shows:
# - Which lines are tested (green)
# - Which lines are NOT tested (red)
# - Coverage percentage per file
```

### Coverage Goals

| Component | Current | Target | Priority |
|-----------|---------|--------|----------|
| `models.py` | ~95% | 100% | ✅ Complete |
| `scraper_async.py` | ~85% | 90%+ | ⚠️ In Progress |
| `main.py` | ~75% | 85%+ | 🔄 Needs Work |
| `data_server.py` | ~90% | 100% | ✅ Near Complete |
| `database.py` | ~60% | 70%+ | ⚠️ Config Only |

### Why These Goals?

- **100% coverage** = Simple code (validation, CRUD)
- **90%+ coverage** = Business logic (scraper, state machines)
- **85%+ coverage** = Complex async code (scheduler, lifecycle)
- **70%+ coverage** = Configuration code (setup, initialization)

---

## 📝 Writing New Tests

### Test Structure (AAA Pattern)

```python
def test_descriptive_name(fixture1, fixture2):
    """
    WHY: Brief explanation of what we're testing
    ARRANGE: What you set up
    ACT: What you do
    ASSERT: What you expect
    """
    # Arrange
    data = {"key": "value"}

    # Act
    result = function_to_test(data)

    # Assert
    assert result == expected_value
```

### Example: Testing a Model

```python
class TestNewFeature:
    """Group related tests in a class."""

    def test_model_creation(self, db_session):
        """
        WHY: Verify model can be created and saved.
        ARRANGE: Valid model data
        ACT: Save to database
        ASSERT: Data is persisted correctly
        """
        # Arrange
        entry = MyModel(field1="value1", field2="value2")

        # Act
        db_session.add(entry)
        db_session.commit()

        # Assert
        saved = db_session.query(MyModel).first()
        assert saved is not None
        assert saved.field1 == "value1"
```

### Example: Testing an Async Function

```python
@pytest.mark.asyncio
async def test_async_function(clean_collection_manager):
    """
    WHY: Test async scraper behavior
    ARRANGE: Mock external dependencies
    ACT: Call async function
    ASSERT: Expected result
    """
    # Arrange
    manager = clean_collection_manager

    # Act
    result = await manager.some_async_method()

    # Assert
    assert result == expected_value
```

### Example: Testing an API Endpoint

```python
def test_endpoint(test_client, db_session):
    """
    WHY: Verify API endpoint works correctly
    ARRANGE: Data in database
    ACT: Make HTTP request
    ASSERT: Response is correct
    """
    # Arrange
    db_session.add(MyModel(field="value"))
    db_session.commit()

    # Act
    response = test_client.get("/my-endpoint")

    # Assert
    assert response.status_code == 200
    assert response.json()["field"] == "value"
```

---

## 🐛 Troubleshooting

### Common Issues

#### 1. ImportError: No module named 'app'

```bash
# Solution: Set PYTHONPATH
export PYTHONPATH=/home/bu/PythonCode/vtrack:$PYTHONPATH

# Or run from project root
cd /home/bu/PythonCode/vtrack
pytest
```

#### 2. Database locked / Permission denied

```bash
# Solution: Ensure test.db is not in use
rm -f test.db
pytest
```

#### 3. Async tests hanging

```bash
# Problem: pytest-asyncio not installed or misconfigured
pip install pytest-asyncio>=0.23.0

# Check pytest.ini has:
# asyncio_mode = auto
```

#### 4. Fixtures not found

```bash
# Problem: conftest.py not in correct location
# Solution: Ensure structure is:
# app/tests/conftest.py
# app/tests/test_*.py
```

#### 5. Mock not working

```python
# Problem: Patching wrong module
# ❌ Wrong:
with patch('httpx.AsyncClient'):

# ✅ Correct:
with patch('app.scraper_async.httpx.AsyncClient'):

# Rule: Patch where it's USED, not where it's DEFINED
```

### Debugging Tests

```bash
# Run with Python debugger
pytest --pdb  # Drops into debugger on failure

# Show print statements
pytest -s

# Show full error traces
pytest -v --tb=long

# Run single test with maximum verbosity
pytest -vv -s --tb=long app/tests/test_models.py::test_specific_function
```

---

## 🎓 Best Practices

### DO ✅

1. **Use descriptive test names**
   ```python
   ✅ test_collection_starts_when_route_status_is_en_recorrido()
   ❌ test_start()
   ```

2. **Follow AAA pattern**
   - Arrange (setup)
   - Act (execute)
   - Assert (verify)

3. **Test one thing per test**
   - Each test should verify ONE behavior
   - Multiple assertions OK if testing same behavior

4. **Use fixtures for setup**
   - Don't repeat setup code
   - Use conftest.py fixtures

5. **Mock external dependencies**
   - HTTP calls
   - File system
   - Time/dates (when needed)

6. **Make tests independent**
   - Tests should NOT depend on other tests
   - Tests should pass in any order

### DON'T ❌

1. **Don't test implementation details**
   ```python
   ❌ assert manager._internal_variable == 5
   ✅ assert manager.get_count() == 5
   ```

2. **Don't use sleep() in tests**
   ```python
   ❌ time.sleep(5)  # Slow!
   ✅ await asyncio.sleep(0.1)  # For async coordination only
   ```

3. **Don't rely on test order**
   ```python
   ❌ test_01_setup(), test_02_action()
   ✅ Use fixtures for setup
   ```

4. **Don't mix unit and integration tests**
   - Keep them separate
   - Use markers to distinguish

5. **Don't skip tests without good reason**
   ```python
   ❌ @pytest.mark.skip  # No reason given
   ✅ @pytest.mark.skip("Bug #123 - waiting for API fix")
   ```

---

## 📈 Next Steps

### Phase 1: Get Tests Running ✅
- [x] Install dependencies
- [x] Run pytest successfully
- [x] Understand test structure

### Phase 2: Improve Coverage ⚠️
- [ ] Run coverage report
- [ ] Identify untested code
- [ ] Add tests for gaps
- [ ] Target: 85%+ coverage

### Phase 3: CI/CD Integration 🔄
- [ ] Set up GitHub Actions
- [ ] Run tests on every commit
- [ ] Block merges if tests fail
- [ ] Generate coverage reports

### Phase 4: Performance Testing 🎯
- [ ] Add load tests
- [ ] Benchmark API response times
- [ ] Test with realistic data volumes
- [ ] Identify bottlenecks

---

## 📚 Additional Resources

### Pytest Documentation
- [Pytest Official Docs](https://docs.pytest.org/)
- [Pytest Fixtures](https://docs.pytest.org/en/latest/fixture.html)
- [Pytest Async](https://pytest-asyncio.readthedocs.io/)

### FastAPI Testing
- [FastAPI Testing Guide](https://fastapi.tiangolo.com/tutorial/testing/)
- [TestClient vs AsyncClient](https://fastapi.tiangolo.com/advanced/async-tests/)

### Mocking
- [unittest.mock Guide](https://docs.python.org/3/library/unittest.mock.html)
- [Mocking Best Practices](https://realpython.com/python-mock-library/)

---

## 🤝 Contributing Tests

When adding new features:

1. Write tests FIRST (TDD approach)
2. Ensure tests fail before implementing feature
3. Implement feature
4. Ensure tests pass
5. Run full test suite
6. Check coverage didn't decrease

### Test Checklist

- [ ] Test follows AAA pattern
- [ ] Test name is descriptive
- [ ] Docstring explains WHY we're testing
- [ ] Uses appropriate fixtures
- [ ] Mocks external dependencies
- [ ] Runs quickly (< 1 second)
- [ ] Passes consistently
- [ ] Added to appropriate test file

---

## 🎉 Success Metrics

Your test suite is production-ready when:

- ✅ All tests pass consistently
- ✅ Tests run in under 10 seconds
- ✅ Coverage is above 85%
- ✅ No flaky tests
- ✅ Tests document how system works
- ✅ Developers trust the tests
- ✅ Refactoring is safe and confident

---

**Remember:** Good tests are your safety net. Invest time in them now, save debugging time later! 🚀
