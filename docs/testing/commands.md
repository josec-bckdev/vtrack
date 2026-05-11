# 🚀 Quick Test Commands Reference

## Essential Commands

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=app --cov-report=term-missing

# Run specific file
pytest app/tests/test_models.py

# Run specific test
pytest app/tests/test_models.py::TestRouteDataEntryModel::test_create_route_data_entry_success
```

## By Test Phase

```bash
# Phase 1: Models (Fast, Foundation)
pytest app/tests/test_models.py -v

# Phase 2: Scraper Logic (Core Business Logic)
pytest app/tests/test_scraper_async.py -v

# Phase 3: API Endpoints (Integration)
pytest app/tests/test_api_endpoints.py -v

# Geofence tests only (location analyzer + geofence integrations)
PYTHONPATH=/home/bu/PythonCode/vtrack/shared-package/src:$PYTHONPATH pytest -m geofence -v
```

## Debugging

```bash
# Stop on first failure
pytest -x

# Show print statements
pytest -s

# Full error traces
pytest --tb=long

# Run only failed tests
pytest --lf
```

## Coverage

```bash
# Terminal report
pytest --cov=app --cov-report=term

# HTML report (open htmlcov/index.html)
pytest --cov=app --cov-report=html

# Missing lines report
pytest --cov=app --cov-report=term-missing
```

## Installation

```bash
# Install all dependencies
pip install -r requirements.txt

# Or just testing dependencies
pip install pytest pytest-asyncio pytest-cov
```
