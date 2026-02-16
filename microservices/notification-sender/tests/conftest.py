"""
Pytest Configuration for Notification Sender Tests

Provides fixtures and mocks for testing the notification sender microservice.
"""

import pytest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, List


@pytest.fixture
def sample_users() -> List[Dict[str, str]]:
    """Sample user configuration for testing"""
    return [
        {"name": "Admin User", "telegram_id": "123456789", "role": "admin"},
        {"name": "Regular User 1", "telegram_id": "987654321", "role": "user"},
        {"name": "Admin User 2", "telegram_id": "111222333", "role": "admin"},
        {"name": "Regular User 2", "telegram_id": "444555666", "role": "user"},
    ]


@pytest.fixture
def temp_users_yaml(sample_users):
    """
    Create a temporary users.yaml file for testing
    
    Returns the path to the temporary file
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.safe_dump({'users': sample_users}, f)
        temp_path = Path(f.name)
    
    yield temp_path
    
    # Cleanup
    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture
def invalid_users_yaml():
    """Create an invalid users.yaml file for testing error handling"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("invalid: yaml: content: [")
        temp_path = Path(f.name)
    
    yield temp_path
    
    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture
def empty_users_yaml():
    """Create a users.yaml with no users"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.safe_dump({'users': []}, f)
        temp_path = Path(f.name)
    
    yield temp_path
    
    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture
def mock_telegram_bot():
    """
    Mock Telegram Bot for testing without actual API calls
    
    Returns a MagicMock that simulates successful message sending
    """
    mock_bot = MagicMock()
    
    # Mock the send_message method to return a successful response
    mock_message = MagicMock()
    mock_message.message_id = 12345
    
    # Create an async mock for send_message
    async def mock_send_message(*args, **kwargs):
        return mock_message
    
    mock_bot.send_message = AsyncMock(side_effect=mock_send_message)
    
    return mock_bot


@pytest.fixture
def sample_alert_data() -> Dict:
    """Sample alert data for testing"""
    return {
        'ruta': 101,
        'alert_type': 'GEOFENCE_ENTRY',
        'area_name': 'Test Zone',
        'severity': 'WARNING',
        'latitude': 4.7110,
        'longitude': -74.0059,
        'timestamp': '2026-02-16 12:00:00'
    }


@pytest.fixture
def mock_settings():
    """Mock settings object"""
    settings = MagicMock()
    settings.TELEGRAM_BOT_TOKEN = "test_bot_token_1234567890"
    settings.TELEGRAM_CHAT_ID = "default_chat_id"
    settings.REDIS_URL = "redis://localhost:6379/0"
    settings.POLL_INTERVAL = 2
    return settings
