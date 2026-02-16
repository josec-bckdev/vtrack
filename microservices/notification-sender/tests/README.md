# Notification Sender Tests

This directory contains tests for the notification-sender microservice.

## Test Structure

```
tests/
├── __init__.py           # Package marker
├── conftest.py          # Shared fixtures and test configuration
├── test_config.py       # Tests for YAML user configuration loading
└── test_telegram.py     # Tests for multi-user Telegram sending
```

## Running Tests

### Run all tests
```bash
cd /home/bu/PythonCode/vtrack/microservices/notification-sender
pytest
```

### Run specific test file
```bash
pytest tests/test_config.py
pytest tests/test_telegram.py
```

### Run specific test class
```bash
pytest tests/test_config.py::TestLoadUsers
pytest tests/test_telegram.py::TestTelegramNotifierSendTest
```

### Run specific test function
```bash
pytest tests/test_config.py::TestLoadUsers::test_load_valid_users
```

### Run with verbose output
```bash
pytest -v
```

### Run with coverage
```bash
pytest --cov=. --cov-report=html
```

## Test Coverage

### test_config.py
Tests for `config.py` and the `load_users()` function:
- ✅ Loading valid YAML configuration
- ✅ Data normalization (telegram_id to string)
- ✅ Error handling for missing file
- ✅ Error handling for empty users list
- ✅ Error handling for invalid YAML syntax
- ✅ Validation of required fields
- ✅ Validation of role values
- ✅ Case normalization for roles

### test_telegram.py
Tests for `providers/telegram.py` and the `TelegramNotifier` class:
- ✅ Initialization with users.yaml
- ✅ Fallback to environment variable
- ✅ Sending alerts to ALL users (admin + regular)
- ✅ Sending test messages to ADMINS ONLY
- ✅ Message formatting with emojis and metadata
- ✅ Error handling for failed sends
- ✅ Partial failure handling (some users succeed, some fail)
- ✅ Behavior when no admin users exist

## Fixtures

Key fixtures defined in `conftest.py`:

- **sample_users**: Sample user configuration data
- **temp_users_yaml**: Temporary users.yaml file for testing
- **invalid_users_yaml**: Invalid YAML for error testing
- **empty_users_yaml**: YAML with no users
- **mock_telegram_bot**: Mocked Telegram Bot (no real API calls)
- **sample_alert_data**: Sample alert data for testing
- **mock_settings**: Mocked settings object

## Test Philosophy

These tests follow the microservice testing pyramid:

1. **Unit Tests** (majority): Test individual functions in isolation
   - Fast execution
   - No external dependencies
   - Mock everything that touches I/O

2. **Integration Tests** (fewer): Test component interactions
   - May use temp files
   - Test real YAML parsing
   - Mock only external services (Telegram API)

3. **End-to-End Tests** (manual): Full flow testing
   - Use `test_full_flow.py` for manual testing
   - Requires real Redis and Telegram credentials

## Adding New Tests

When adding new features to the notification-sender:

1. Add fixtures to `conftest.py` if needed
2. Create test class following naming convention `Test{ClassName}`
3. Write test methods starting with `test_`
4. Use descriptive test names that explain what is being tested
5. Follow AAA pattern: Arrange, Act, Assert

Example:
```python
def test_new_feature_does_something(self, fixture1, fixture2):
    """Test that new feature behaves as expected"""
    # Arrange
    notifier = TelegramNotifier()
    
    # Act
    result = notifier.new_method()
    
    # Assert
    assert result is True
```

## Troubleshooting

### Import Errors
If you get import errors, make sure you're running pytest from the microservice directory:
```bash
cd /home/bu/PythonCode/vtrack/microservices/notification-sender
pytest
```

### Mock Issues
If mocks aren't working, verify the patch path matches the import path used in the module being tested.

### Async Test Errors
For testing async code, use `AsyncMock` from `unittest.mock` and `asyncio.run()` to execute coroutines.
