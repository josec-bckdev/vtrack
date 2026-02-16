# Testing the Multi-User Notification Feature

## Quick Start

### 1. Install Test Dependencies
```bash
cd /home/bu/PythonCode/vtrack/microservices/notification-sender
pip install -r requirements.txt
```

### 2. Run All Tests
```bash
pytest
```

### 3. Run Integration Test (Manual)
```bash
# Test YAML loading only
python tests/test_integration.py --yaml-only

# Full integration test
python tests/test_integration.py
```

## Test Structure

```
microservices/notification-sender/
├── tests/                      # ✅ NEW: Test directory for this microservice
│   ├── __init__.py            # Package marker
│   ├── conftest.py            # Pytest fixtures and test configuration
│   ├── test_config.py         # Tests for YAML configuration loading
│   ├── test_telegram.py       # Tests for multi-user Telegram sending
│   ├── test_integration.py    # Manual integration tests
│   └── README.md              # Test documentation
├── pytest.ini                 # ✅ NEW: Pytest configuration
└── requirements.txt           # ✅ UPDATED: Added pytest dependencies
```

## What's Being Tested

### 1. YAML Configuration (`test_config.py`)
- ✅ Loading valid users.yaml
- ✅ Validation of required fields (name, telegram_id, role)
- ✅ Role validation (must be 'admin' or 'user')
- ✅ Error handling for missing/invalid files
- ✅ Data normalization (telegram_id → string)

### 2. Multi-User Telegram Sending (`test_telegram.py`)
- ✅ Initialization with multiple users
- ✅ Sending alerts to ALL users (admins + regular users)
- ✅ Sending test messages to ADMINS ONLY
- ✅ Message formatting with emojis and metadata
- ✅ Handling partial failures (some users succeed, some fail)
- ✅ Fallback to legacy TELEGRAM_CHAT_ID

### 3. Integration Tests (`test_integration.py`)
- ✅ End-to-end YAML loading
- ✅ TelegramNotifier initialization
- ✅ Message formatting verification
- ✅ Admin filtering for test messages

## Test Commands Reference

```bash
# Run all tests with verbose output
pytest -v

# Run specific test file
pytest tests/test_config.py
pytest tests/test_telegram.py

# Run specific test class
pytest tests/test_config.py::TestLoadUsers
pytest tests/test_telegram.py::TestTelegramNotifierSendTest

# Run specific test
pytest tests/test_config.py::TestLoadUsers::test_load_valid_users

# Run with coverage report
pytest --cov=. --cov-report=html

# Run only unit tests (fast)
pytest -m unit

# Run integration tests
pytest -m integration
```

## Expected Test Output

```
========================== test session starts ==========================
platform linux -- Python 3.x.x, pytest-7.x.x
collected 25 items

tests/test_config.py ................                            [ 64%]
tests/test_telegram.py .........                                [ 100%]

========================== 25 passed in 2.13s ===========================
```

## Troubleshooting

### Import Errors
```bash
# Make sure you're in the right directory
cd /home/bu/PythonCode/vtrack/microservices/notification-sender
pytest
```

### Module Not Found
```bash
# Install dependencies
pip install -r requirements.txt
```

### Tests Hanging
- Check if you have infinite loops in async code
- Use `pytest --timeout=10` to set timeout

## Best Practices for Microservice Testing

✅ **Each microservice has its own `tests/` folder**
- Keeps tests isolated and independent
- Can test each service without dependencies
- Supports independent deployment

✅ **Use fixtures for common setup**
- Defined in `conftest.py`
- Reusable across test files
- Keeps tests DRY (Don't Repeat Yourself)

✅ **Mock external dependencies**
- No real Telegram API calls in unit tests
- Use temporary files for YAML testing
- Fast, reliable, repeatable tests

✅ **Integration tests are separate**
- Manual tests in `test_integration.py`
- Can be run when needed
- May require real credentials/services

## Adding More Microservices

When you add tests to other microservices (like `alert-processor`):

```bash
# Create test structure
mkdir microservices/alert-processor/tests
touch microservices/alert-processor/tests/__init__.py
touch microservices/alert-processor/tests/conftest.py
touch microservices/alert-processor/tests/test_processor.py
cp microservices/notification-sender/pytest.ini microservices/alert-processor/

# Run tests for that microservice
cd microservices/alert-processor
pytest
```

Each microservice is independently testable! 🎉
