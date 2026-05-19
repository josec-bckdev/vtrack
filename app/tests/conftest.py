"""
Pytest Configuration for VTRACK Test Suite

This file provides fixtures and configuration for testing the VTRACK application.
We use SQLite in-memory database for speed and isolation.

Senior Dev Note: conftest.py is automatically discovered by pytest and makes fixtures
available to all test files in this directory and subdirectories.
"""

# CRITICAL: Set TESTING environment variable BEFORE any imports
# This ensures app.database uses SQLite instead of PostgreSQL
import os
os.environ["TESTING"] = "1"

import pytest
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Generator, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

import fakeredis
import redis

from app.main import app
from app.database import get_db
from app.models import Base, ScrapingResponse
from app.scraper_async import AsyncCollectionManager


# =============================================================================
# DATABASE FIXTURES
# =============================================================================

@pytest.fixture(scope="session")
def test_engine():
    """
    Creates a SQLite in-memory engine for the entire test session.

    Why SQLite for testing?
    - Blazing fast (in-memory)
    - No external dependencies
    - Perfect isolation between test runs
    - Same SQL dialect for most operations

    Why StaticPool?
    - Keeps the in-memory DB alive across connections
    - Without it, each new connection would create a fresh empty DB

    Why scope="session"?
    - Creates the engine once for all tests
    - Saves setup/teardown time
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # Critical for in-memory SQLite!
    )

    # Enable foreign key constraints in SQLite (disabled by default)
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Create all tables once
    Base.metadata.create_all(bind=engine)

    yield engine

    # Cleanup: Drop all tables after all tests
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(test_engine) -> Generator[Session, None, None]:
    """
    Provides a clean database session for each test function.

    Why scope="function"?
    - Each test gets a fresh transaction
    - Tests cannot interfere with each other
    - Automatic rollback ensures isolation

    The Pattern (Critical for test isolation):
    1. Begin a transaction
    2. Run the test
    3. Rollback the transaction (undo everything)
    4. Close the session

    This is faster than recreating tables and ensures no test data leaks.
    """
    # Create a connection and begin a transaction
    connection = test_engine.connect()
    transaction = connection.begin()

    # Create a session bound to this connection
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=connection)
    session = TestingSessionLocal()

    yield session

    # Cleanup: rollback and close
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function", autouse=True)
def override_get_db(db_session: Session):
    """
    Overrides the FastAPI dependency to use our test database.

    Why this matters:
    - FastAPI's Depends(get_db) will now use our test DB instead of production
    - All API endpoints automatically use the test session
    - No need to modify production code for testing

    autouse=True means this runs automatically for every test!
    """
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass  # Session cleanup handled by db_session fixture

    app.dependency_overrides[get_db] = _override_get_db

    yield

    app.dependency_overrides.clear()


# =============================================================================
# FASTAPI TEST CLIENT FIXTURES
# =============================================================================

@pytest.fixture(scope="function")
def test_client(override_get_db) -> Generator[TestClient, None, None]:
    """
    Provides a synchronous test client for FastAPI endpoints.

    When to use TestClient vs AsyncClient?
    - TestClient: For simple, synchronous endpoint tests (faster)
    - AsyncClient: For testing async endpoints or when you need async context

    The override_get_db dependency ensures this client uses our test database.
    """
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="function")
async def async_test_client(override_get_db) -> AsyncGenerator[AsyncClient, None]:
    """
    Provides an async test client for testing async FastAPI endpoints.

    Why async client?
    - Tests endpoints that use async/await
    - Can test WebSocket connections
    - More realistic for testing background tasks

    Note: Requires pytest-asyncio to work properly.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# =============================================================================
# MOCK FIXTURES FOR EXTERNAL API CALLS
# =============================================================================

@pytest.fixture
def mock_scraper_credentials(monkeypatch):
    """
    Mocks scraper credentials as environment variables.

    Why mock credentials?
    - Tests shouldn't depend on real credentials
    - Prevents accidental exposure of secrets
    - Makes tests portable across environments
    """
    monkeypatch.setenv("SCRAPER_EMAIL", "test@example.com")
    monkeypatch.setenv("SCRAPER_PASSWORD", "test_password_123")


@pytest.fixture
def mock_successful_login_response():
    """
    Provides a mock successful login response from the external service.

    Senior Dev Note: When mocking HTTP responses, match the structure
    exactly as the real API returns it. This prevents subtle bugs.
    """
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.cookies = {"session_id": "test_session_12345"}
    return mock_response


@pytest.fixture
def mock_valores_data():
    """
    Mock data for the 'valores' endpoint (position data).

    Structure matches the real API response from rutasljrj.net
    Format: [ruta, name, latitude, longitude, img, timestamp]
    """
    return [
        ["101", "Ruta 101", "4.6097", "-74.0817", "img.png", "2025-01-15 08:30:00"]
    ]


@pytest.fixture
def mock_estados_data():
    """
    Mock data for the 'estados' endpoint (status data).

    Structure matches the real API response from rutasljrj.net
    Format: [id, route_status, route_status_ts, student_id, student_name, student_status, student_status_ts]
    """
    return [
        ["1", "En recorrido", "2025-01-15 08:30:00", "439", "Student Name", "Bajo", "2025-01-15 08:35:00"]
    ]


@pytest.fixture
def mock_scraping_response(mock_valores_data, mock_estados_data):
    """
    Creates a complete ScrapingResponse object for testing.

    This represents what our scraper returns after fetching from the external API.
    """
    return ScrapingResponse(
        source="rutasljrj.net",
        valores_data=mock_valores_data,
        estados_data=mock_estados_data
    )


@pytest.fixture
def mock_httpx_client(mock_successful_login_response, mock_valores_data, mock_estados_data):
    """
    Mocks the httpx.AsyncClient for testing scraper without hitting real API.

    Senior Dev Note: This is the KEY fixture for testing scrapers!
    - We mock the HTTP client, not the entire scraper
    - This tests our scraper logic while avoiding external dependencies
    - Each post() call returns appropriate mock data based on the URL

    Pattern: Mock at the I/O boundary (HTTP), test everything above it.
    """
    mock_client = AsyncMock()

    async def mock_post(url, data=None, **kwargs):
        """Mock post method that returns different responses based on URL."""
        response = AsyncMock()

        # Login endpoint
        if "login/validacion" in url:
            response.status_code = 200
            response.cookies = {"PHPSESSID": "mock_session_123"}
            return response

        # Valores endpoint
        elif "actualizaValores" in url:
            response.status_code = 200
            response.json = MagicMock(return_value=mock_valores_data)  # json() is NOT async
            response.raise_for_status = MagicMock()
            return response

        # Estados endpoint
        elif "obtieneEstados" in url:
            response.status_code = 200
            response.json = MagicMock(return_value=mock_estados_data)  # json() is NOT async
            response.raise_for_status = MagicMock()
            return response

        # Default fallback
        response.status_code = 404
        return response

    mock_client.post = mock_post
    mock_client.cookies = MagicMock()
    mock_client.cookies.set = MagicMock()

    return mock_client


# =============================================================================
# COLLECTION MANAGER FIXTURES
# =============================================================================

@pytest.fixture
def clean_collection_manager():
    """
    Provides a fresh AsyncCollectionManager with a mock repository.

    Uses MagicMock(spec=IRouteDataRepository) so no DB is needed.
    create_task returns 1 so current_task_id is a valid int for Pydantic.
    """
    from unittest.mock import MagicMock
    from app.domain.ports import IRouteDataRepository
    from app.adapters.collection_state import InMemoryCollectionState

    mock_repo = MagicMock(spec=IRouteDataRepository)
    mock_repo.create_task.return_value = 1

    manager = AsyncCollectionManager(repository=mock_repo, state_store=InMemoryCollectionState())
    manager._task = None
    manager._is_running = False
    manager._last_login_time = None
    manager._session_cookies = None

    return manager


@pytest.fixture
def collection_manager_with_db(db_session):
    """
    Provides an AsyncCollectionManager wired to the in-memory test DB.

    Use this fixture only for tests that assert on actual database state.
    For all other manager tests, prefer clean_collection_manager.
    """
    from app.adapters.route_repository import SqlAlchemyRouteRepository
    from app.adapters.collection_state import InMemoryCollectionState

    repo = SqlAlchemyRouteRepository(get_session=lambda: db_session)
    manager = AsyncCollectionManager(repository=repo, state_store=InMemoryCollectionState())
    manager._task = None
    manager._is_running = False
    manager._last_login_time = None
    manager._session_cookies = None

    return manager


# =============================================================================
# REDIS AND MESSAGE QUEUE FIXTURES
# =============================================================================

@pytest.fixture(scope="function")
def fake_redis_client():
    """
    Provides a fakeredis client for testing Redis operations.

    Why fakeredis instead of real Redis?
    - No external dependencies needed for tests
    - Lightning fast (in-memory)
    - Perfect test isolation (fresh instance per test)
    - Same API as real Redis, so tests are realistic

    fakeredis supports: strings, lists, sets, hashes, sorted sets, etc.
    """
    # Create a fresh fakeredis instance for this test
    client = fakeredis.FakeStrictRedis(decode_responses=True)
    yield client
    # Cleanup: flush all data
    client.flushall()


@pytest.fixture(scope="function")
def redis_url_test(monkeypatch, fake_redis_client):
    """
    Configures the test to use fakeredis instead of real Redis.

    This fixture:
    1. Patches the REDIS_URL to point to our fake client
    2. Makes all code using Redis use fakeredis automatically
    3. Provides test isolation
    """
    # Monkeypatch redis.from_url to return our fake client
    def mock_from_url(url, decode_responses=True):
        return fake_redis_client
    
    monkeypatch.setattr("redis.from_url", mock_from_url)
    
    return "redis://localhost:6379/0"


@pytest.fixture(scope="function")
def message_queue_fixture(fake_redis_client):
    """
    Provides a fresh MessageQueue instance for testing.

    Why pass the fake_redis_client?
    - Ensures the queue uses our test Redis, not production
    - Allows us to inspect/manipulate the queue in tests
    - Maintains test isolation
    """
    from shared.message_queue import MessageQueue
    from unittest.mock import MagicMock, patch
    from rq import Queue
    
    # Create queue with patched connection to avoid real Redis ping
    with patch('redis.from_url') as mock_redis:
        # Use our fake redis client
        mock_redis.return_value = fake_redis_client
        queue = MessageQueue("redis://localhost:6379/0")
    
    return queue


@pytest.fixture(scope="function")
def location_analyzer_fixture():
    """
    Provides a fresh LocationAnalyzer instance for testing.

    The LocationAnalyzer initializes with default zones:
    - School Zone
    - Dangerous Area
    - Route Depot

    Why fresh instance?
    - Tests shouldn't share state
    - Tracking state persists across calls, so fresh instance ensures isolation
    """
    from shared.location_alerts import LocationAnalyzer
    
    analyzer = LocationAnalyzer()
    return analyzer


@pytest.fixture(scope="function")
def sample_zones():
    """
    Provides sample geofence zones for testing.

    These represent the YAML-configured zones used by the application.
    """
    from shared.location_alerts import Zone, AlertType, AlertSeverity
    
    return {
        'cota': Zone(
            zone_id=1,
            name="Cota-conejera",
            latitude=4.767916,
            longitude=-74.07654149999999,
            radius_meters=1500,
            alert_type=AlertType.GEOFENCE_EXIT,
            severity=AlertSeverity.WARNING,
            enabled=True
        ),
        'boyaca': Zone(
            zone_id=2,
            name="Boyaca",
            latitude=4.742,
            longitude=-74.065845,
            radius_meters=1600,
            alert_type=AlertType.GEOFENCE_ENTRY,
            severity=AlertSeverity.WARNING,
            enabled=True
        ),
        'prado': Zone(
            zone_id=3,
            name="Prado",
            latitude=4.7186734999999995,
            longitude=-74.062382,
            radius_meters=1200,
            alert_type=AlertType.GEOFENCE_ENTRY,
            severity=AlertSeverity.WARNING,
            enabled=True
        ),
    }


@pytest.fixture(scope="function")
def coordinate_data_fixtures():
    """
    Provides sample coordinate data at various locations.

    These coordinates are strategically placed to test:
    - Inside zones (should trigger alerts)
    - Outside zones (should not trigger alerts)
    - Zone boundaries
    """
    return {
        # Inside School Zone (4.7110, -74.0059, 500m radius)
        'inside_school': {
            'ruta': 101,
            'latitude': 4.7110,
            'longitude': -74.0059,
        },
        # Near but outside School Zone
        'near_school': {
            'ruta': 101,
            'latitude': 4.7130,
            'longitude': -74.0059,
        },
        # Inside Dangerous Area (4.6289, -74.0832, 1000m radius)
        'inside_dangerous': {
            'ruta': 102,
            'latitude': 4.6289,
            'longitude': -74.0832,
        },
        # Outside all zones
        'outside_all': {
            'ruta': 103,
            'latitude': 3.4000,
            'longitude': -76.5000,
        },
        # Inside Depot (4.5500, -74.1000, 750m radius)
        'inside_depot': {
            'ruta': 104,
            'latitude': 4.5500,
            'longitude': -74.1000,
        },
    }


# =============================================================================
# TIME AND DATA FIXTURES
# =============================================================================

@pytest.fixture
def bogota_time():
    """Returns current time in America/Bogota timezone."""
    return datetime.now(ZoneInfo("America/Bogota"))


@pytest.fixture
def sample_route_data():
    """
    Sample normalized route data for testing.

    This matches the structure returned by normalize_route_data()
    """
    return {
        'ruta': 101,
        'ns_latitude': 4.6097,
        'ew_longitude': -74.0817,
        'position_ts': datetime(2025, 1, 15, 8, 30, 0, tzinfo=ZoneInfo("America/Bogota")),
        'route_status': "En recorrido",
        'route_status_ts': datetime(2025, 1, 15, 8, 30, 0, tzinfo=ZoneInfo("America/Bogota")),
        'student_status': "Bajo",
        'student_status_ts': datetime(2025, 1, 15, 8, 35, 0, tzinfo=ZoneInfo("America/Bogota")),
    }


# =============================================================================
# PYTEST CONFIGURATION
# =============================================================================

@pytest.fixture(scope="session")
def event_loop_policy():
    """
    Sets the event loop policy for async tests.

    Why this matters:
    - pytest-asyncio needs an event loop policy
    - This ensures consistent async behavior across tests
    """
    return asyncio.get_event_loop_policy()


# Configure pytest-asyncio
def pytest_configure(config):
    """Pytest configuration hook."""
    config.addinivalue_line(
        "markers", "asyncio: mark test as an async test"
    )

    # Note: No need to mock database or managers anymore since TESTING=1
    # ensures SQLite is used, and individual tests handle their own mocking
