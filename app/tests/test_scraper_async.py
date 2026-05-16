"""
Test Suite for Async Scraper Logic

Tests the AsyncCollectionManager and related scraper functions.

Why test the scraper?
- It's the core business logic of VTRACK
- Complex async operations are error-prone
- External API calls must be mocked to avoid real network calls
- Session management and state transitions need careful testing

Key Testing Challenge: The scraper runs in a while loop
Solution: Mock external calls and control loop iterations
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import RequestError, HTTPStatusError

from app.scraper_async import (
    AsyncCollectionManager,
    parse_remote_datetime,
    normalize_route_data,
    COLLECTION_INTERVAL_SECONDS,
)
from app.models import (
    RouteDataEntry,
    CollectionMetadata,
    CollectionStatusEnum,
    ScrapingResponse,
)


# =============================================================================
# UTILITY FUNCTION TESTS
# =============================================================================

class TestParseRemoteDateTime:
    """Tests for parse_remote_datetime utility function."""

    def test_valid_datetime_string(self):
        """
        WHY: External API returns timestamps as strings.
        ARRANGE: Valid datetime string
        ACT: Parse it
        ASSERT: Returns timezone-aware datetime
        """
        # Arrange
        date_string = "2025-01-15 08:30:00"

        # Act
        result = parse_remote_datetime(date_string)

        # Assert
        assert result is not None
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 8
        assert result.minute == 30
        assert result.tzinfo is not None  # Timezone aware

    def test_invalid_date_returns_none(self):
        """
        WHY: API returns '0000-00-00 00:00:00' for missing dates.
        ARRANGE: Invalid date string
        ACT: Parse it
        ASSERT: Returns None (not an exception)
        """
        # Arrange
        date_string = "0000-00-00 00:00:00"

        # Act
        result = parse_remote_datetime(date_string)

        # Assert
        assert result is None

    def test_malformed_datetime_returns_none(self):
        """
        WHY: Defensive programming - handle unexpected formats.
        ARRANGE: Malformed datetime string
        ACT: Parse it
        ASSERT: Returns None and logs warning
        """
        # Arrange
        date_string = "not-a-date"

        # Act
        result = parse_remote_datetime(date_string)

        # Assert
        assert result is None


class TestNormalizeRouteData:
    """Tests for normalize_route_data function."""

    def test_valid_data_normalization(self):
        """
        WHY: Raw API data needs to be transformed into our format.
        ARRANGE: Valid valores and estados data
        ACT: Normalize it
        ASSERT: Returns correctly structured dict
        """
        # Arrange
        valores_data = [
            ["101", "Ruta 101", "4.6097", "-74.0817", "img.png", "2025-01-15 08:30:00"]
        ]
        estados_data = [
            ["1", "En recorrido", "2025-01-15 08:30:00", "439", "Student", "Subio", "2025-01-15 08:35:00"]
        ]

        # Act
        result = normalize_route_data(valores_data, estados_data)

        # Assert
        assert result is not None
        assert result['ruta'] == 101
        assert result['ns_latitude'] == 4.6097
        assert result['ew_longitude'] == -74.0817
        assert result['route_status'] == "En recorrido"
        assert result['student_status'] == "Subio"
        assert isinstance(result['position_ts'], datetime)

    def test_empty_data_returns_none(self):
        """
        WHY: API might return empty arrays when no data available.
        ARRANGE: Empty data arrays
        ACT: Normalize them
        ASSERT: Returns None
        """
        # Arrange
        valores_data = []
        estados_data = []

        # Act
        result = normalize_route_data(valores_data, estados_data)

        # Assert
        assert result is None

    def test_invalid_date_handled_gracefully(self):
        """
        WHY: Invalid dates should be converted to None, not crash.
        ARRANGE: Data with 0000-00-00 dates
        ACT: Normalize it
        ASSERT: Datetime fields are None
        """
        # Arrange
        valores_data = [
            ["101", "Ruta 101", "4.6097", "-74.0817", "img.png", "0000-00-00 00:00:00"]
        ]
        estados_data = [
            ["1", "En recorrido", "0000-00-00 00:00:00", "439", "Student", "Subio", "0000-00-00 00:00:00"]
        ]

        # Act
        result = normalize_route_data(valores_data, estados_data)

        # Assert
        assert result is not None
        assert result['position_ts'] is None
        assert result['route_status_ts'] is None
        assert result['student_status_ts'] is None

    def test_malformed_data_returns_none(self):
        """
        WHY: Defensive - handle unexpected API responses.
        ARRANGE: Data with invalid types
        ACT: Normalize it
        ASSERT: Returns None (doesn't crash)
        """
        # Arrange
        valores_data = [["invalid", "data"]]  # Too few fields
        estados_data = [["also", "invalid"]]

        # Act
        result = normalize_route_data(valores_data, estados_data)

        # Assert
        assert result is None


# =============================================================================
# SESSION MANAGEMENT TESTS
# =============================================================================

class TestSessionManagement:
    """Tests for session management in AsyncCollectionManager."""

    @pytest.mark.asyncio
    async def test_trigger_cookie_refresh_succeeds(self, clean_collection_manager):
        """
        WHY: _trigger_cookie_refresh delegates to run_refresh; success means
             the cookie refresh use case completed and stored cookies.
        """
        manager = clean_collection_manager
        with patch('app.cookie_refresh.run_refresh', new=AsyncMock(return_value=True)):
            result = await manager._trigger_cookie_refresh()
        assert result is True

    @pytest.mark.asyncio
    async def test_trigger_cookie_refresh_fails(self, clean_collection_manager):
        """
        WHY: If the VNC browser automation fails, _trigger_cookie_refresh
             must propagate failure so callers can handle it.
        """
        manager = clean_collection_manager
        with patch('app.cookie_refresh.run_refresh', new=AsyncMock(return_value=False)):
            result = await manager._trigger_cookie_refresh()
        assert result is False

    def test_session_validity_check_fresh_session(self, clean_collection_manager):
        """
        WHY: Fresh sessions should be considered valid.
        ARRANGE: Manager with recent login
        ACT: Check if session is valid
        ASSERT: Returns True
        """
        # Arrange
        manager = clean_collection_manager
        manager._last_login_time = datetime.now(ZoneInfo("America/Bogota"))
        manager._session_cookies = {"PHPSESSID": "test123"}

        # Act
        is_valid = manager._is_session_valid()

        # Assert
        assert is_valid is True

    def test_session_validity_check_expired_session(self, clean_collection_manager):
        """
        WHY: Old sessions should be considered invalid.
        ARRANGE: Manager with 13-hour old login (expires at 12 hours)
        ACT: Check if session is valid
        ASSERT: Returns False
        """
        # Arrange
        manager = clean_collection_manager
        manager._last_login_time = datetime.now(ZoneInfo("America/Bogota")) - timedelta(hours=13)
        manager._session_cookies = {"PHPSESSID": "test123"}

        # Act
        is_valid = manager._is_session_valid()

        # Assert
        assert is_valid is False

    def test_session_validity_no_session(self, clean_collection_manager):
        """
        WHY: No session means not valid.
        ARRANGE: Manager with no session
        ACT: Check validity
        ASSERT: Returns False
        """
        # Arrange
        manager = clean_collection_manager

        # Act
        is_valid = manager._is_session_valid()

        # Assert
        assert is_valid is False


# =============================================================================
# DATA FETCHING TESTS
# =============================================================================

class TestDataFetching:
    """Tests for fetching data from external API."""

    @pytest.mark.asyncio
    async def test_fetch_with_valid_session_returns_response(
        self,
        clean_collection_manager,
        mock_httpx_client,
    ):
        """
        WHY: With a valid session already in place, _fetch_remote_data_async
             must return a ScrapingResponse without triggering cookie refresh.
        """
        manager = clean_collection_manager
        # Pre-load a valid session so _ensure_valid_session skips cookie refresh
        manager._session_cookies = {"cf_clearance": "cf_test", "ci_session": "ci_test"}
        manager._last_login_time = datetime.now(ZoneInfo("America/Bogota"))
        # Inject the mock httpx client so no real network call is made
        mock_httpx_client.aclose = AsyncMock()
        manager._client = mock_httpx_client

        result = await manager._fetch_remote_data_async()

        assert isinstance(result, ScrapingResponse)
        assert result.source == "rutasljrj.net"
        assert len(result.valores_data) > 0
        assert len(result.estados_data) > 0

    @pytest.mark.asyncio
    async def test_fetch_raises_when_cookie_refresh_fails(self, clean_collection_manager):
        """
        WHY: If _trigger_cookie_refresh returns False, _fetch_remote_data_async
             must raise RequestError so the collection loop can handle it.
        """
        manager = clean_collection_manager
        # No valid session; mock refresh to fail
        with patch.object(manager, '_trigger_cookie_refresh', new=AsyncMock(return_value=False)):
            with pytest.raises(RequestError):
                await manager._fetch_remote_data_async()


# =============================================================================
# COLLECTION STATE MACHINE TESTS
# =============================================================================

class TestCollectionStateMachine:
    """Tests for state transitions and collection logic."""

    def test_should_start_collection_when_en_recorrido(self, clean_collection_manager):
        """
        WHY: Collection starts when route status is 'En recorrido'.
        ARRANGE: Normalized data with 'En recorrido' status
        ACT: Check if should start
        ASSERT: Returns True
        """
        # Arrange
        manager = clean_collection_manager
        normalized_data = {'route_status': 'En recorrido'}

        # Act
        should_start = manager._should_start_collection(normalized_data)

        # Assert
        assert should_start is True

    def test_should_not_start_collection_other_status(self, clean_collection_manager):
        """
        WHY: Collection should NOT start for other statuses.
        ARRANGE: Data with different status
        ACT: Check if should start
        ASSERT: Returns False
        """
        # Arrange
        manager = clean_collection_manager
        normalized_data = {'route_status': 'Detenido'}

        # Act
        fixed_dt = datetime(2025, 1, 15, 12, 0, 0, tzinfo=ZoneInfo("America/Bogota"))
        with patch("app.scraper_async.datetime") as mock_datetime:
            mock_datetime.now.return_value = fixed_dt
            should_start = manager._should_start_collection(normalized_data)

        # Assert
        assert should_start is False

    def test_check_data_changed_first_call(self, clean_collection_manager):
        """
        WHY: First data point should always be considered 'changed'.
        ARRANGE: Manager with no previous data hash
        ACT: Check if data changed
        ASSERT: Returns True
        """
        # Arrange
        manager = clean_collection_manager
        normalized_data = {
            'ns_latitude': 4.6097,
            'ew_longitude': -74.0817,
            'route_status': 'En recorrido',
            'student_status': 'Subio'
        }

        # Act
        changed = manager._check_data_changed(normalized_data)

        # Assert
        assert changed is True

    def test_check_data_not_changed_same_values(self, clean_collection_manager):
        """
        WHY: Duplicate data should not be saved (bandwidth/storage optimization).
        ARRANGE: Same data called twice
        ACT: Check second call
        ASSERT: Returns False
        """
        # Arrange
        manager = clean_collection_manager
        normalized_data = {
            'ns_latitude': 4.6097,
            'ew_longitude': -74.0817,
            'route_status': 'En recorrido',
            'student_status': 'Subio'
        }

        # Act
        first_call = manager._check_data_changed(normalized_data)
        second_call = manager._check_data_changed(normalized_data)

        # Assert
        assert first_call is True
        assert second_call is False

    def test_check_data_changed_different_position(self, clean_collection_manager):
        """
        WHY: Position changes should trigger data save.
        ARRANGE: Data with different coordinates
        ACT: Check if changed
        ASSERT: Returns True
        """
        # Arrange
        manager = clean_collection_manager
        data1 = {
            'ns_latitude': 4.6097,
            'ew_longitude': -74.0817,
            'route_status': 'En recorrido',
            'student_status': 'Subio'
        }
        data2 = {
            'ns_latitude': 4.6100,  # Changed
            'ew_longitude': -74.0820,  # Changed
            'route_status': 'En recorrido',
            'student_status': 'Subio'
        }

        # Act
        manager._check_data_changed(data1)
        changed = manager._check_data_changed(data2)

        # Assert
        assert changed is True


# =============================================================================
# ASYNC COLLECTION MANAGER LIFECYCLE TESTS
# =============================================================================

class TestAsyncCollectionManagerLifecycle:
    """Tests for start/stop lifecycle of AsyncCollectionManager."""

    @pytest.mark.asyncio
    async def test_start_collection_initializes_metadata(
        self,
        clean_collection_manager,
        db_session,
        mock_scraper_credentials,
        mock_httpx_client
    ):
        """
        WHY: Starting collection should create a metadata record.
        ARRANGE: Clean manager
        ACT: Start collection
        ASSERT: Metadata is created in database
        """
        # Arrange
        manager = clean_collection_manager

        # Mock the collection loop to exit immediately
        async def mock_loop():
            await asyncio.sleep(0.1)
            manager._is_running = False

        # Act
        with patch.object(manager, '_collection_loop', side_effect=mock_loop):
            await manager.start()
            await asyncio.sleep(0.2)  # Let it initialize

        # Assert
        assert manager.current_task_id is not None
        assert manager.start_time is not None
        assert manager.datapoints_collected == 0

        # Check database
        metadata = db_session.query(CollectionMetadata).first()
        assert metadata is not None
        assert metadata.status == CollectionStatusEnum.IDLE.value

    @pytest.mark.asyncio
    async def test_cannot_start_if_already_running(self, clean_collection_manager):
        """
        WHY: Prevent multiple concurrent collections.
        ARRANGE: Manager already running
        ACT: Try to start again
        ASSERT: Raises RuntimeError
        """
        # Arrange
        manager = clean_collection_manager
        manager._is_running = True

        # Act & Assert
        with pytest.raises(RuntimeError, match="already running"):
            await manager.start()

    @pytest.mark.asyncio
    async def test_stop_collection_updates_status(
        self,
        clean_collection_manager,
        db_session,
        mock_scraper_credentials
    ):
        """
        WHY: Stopping should mark collection as FINISHED.
        ARRANGE: Running manager
        ACT: Stop it
        ASSERT: Status updated to FINISHED
        """
        # Arrange
        manager = clean_collection_manager

        # Mock initialization
        async def mock_loop():
            while manager._is_running:
                await asyncio.sleep(0.1)

        with patch.object(manager, '_collection_loop', side_effect=mock_loop):
            await manager.start()
            await asyncio.sleep(0.2)

        # Act
        await manager.stop()

        # Assert
        assert manager._is_running is False
        assert manager._status == CollectionStatusEnum.FINISHED
        assert manager.stop_time is not None

    @pytest.mark.asyncio
    async def test_get_status_returns_current_state(self, clean_collection_manager):
        """
        WHY: Status endpoint needs accurate information.
        ARRANGE: Manager with no active task
        ACT: Get status
        ASSERT: Returns CollectionStatusResponse
        """
        # Arrange
        manager = clean_collection_manager

        # Act
        status = await manager.get_status()

        # Assert
        assert status.status == CollectionStatusEnum.IDLE
        assert status.task_id is None
        assert "No active collection" in status.message

    @pytest.mark.asyncio
    async def test_save_route_data_increments_counter(
        self,
        clean_collection_manager,
        db_session,
        sample_route_data,
        mock_scraper_credentials
    ):
        """
        WHY: Each saved datapoint should increment the counter.
        ARRANGE: Manager with initialized task
        ACT: Save route data
        ASSERT: Counter increments and data is in DB
        """
        # Arrange
        manager = clean_collection_manager

        # Initialize metadata
        async def mock_loop():
            await asyncio.sleep(0.1)
            manager._is_running = False

        with patch.object(manager, '_collection_loop', side_effect=mock_loop):
            await manager.start()
            await asyncio.sleep(0.2)

        # Act
        await manager._save_route_data_async(sample_route_data)

        # Assert
        assert manager.datapoints_collected == 1

        # Check database
        route_entry = db_session.query(RouteDataEntry).first()
        assert route_entry is not None
        assert route_entry.ruta == sample_route_data['ruta']
