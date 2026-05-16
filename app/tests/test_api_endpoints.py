"""
Test Suite for FastAPI Endpoints (Integration Tests)

Tests both main.py (collection control) and data_server.py (data retrieval) endpoints.

Why test endpoints last?
- They depend on models and business logic working correctly
- Integration tests verify the full stack works together
- API contracts must remain stable for clients

These are INTEGRATION tests - they test the full request/response cycle.
"""

import pytest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import patch, AsyncMock

from fastapi import status

from app.models import (
    RouteDataEntry,
    CollectionMetadata,
    CollectionStatusEnum,
    ScrapingResponse,
)


# =============================================================================
# COLLECTION CONTROL ENDPOINT TESTS (main.py)
# =============================================================================

class TestCollectionControlEndpoints:
    """Tests for /collect/* endpoints."""

    def test_start_collection_success(self, test_client, mock_scraper_credentials):
        """
        WHY: Users need to manually start data collection.
        ARRANGE: Clean state, no collection running
        ACT: POST to /collect/start
        ASSERT: Returns 200 with CollectionStatusResponse
        """
        # Arrange - mock the collection manager
        from app.models import CollectionStatusResponse

        with patch('app.main.collection_manager.start') as mock_start:
            mock_start.return_value = True
            with patch('app.main.collection_manager._is_running', False):
                with patch('app.main.collection_manager.get_status') as mock_status:
                    # Return a proper response object with all required fields
                    mock_status.return_value = CollectionStatusResponse(
                        task_id=1,
                        status=CollectionStatusEnum.IDLE,
                        message="Collection started",
                        datapoints_collected=0,
                        start_time=None,
                        stop_time=None,
                        scheduler_running=None,
                        scheduled_times=None
                    )

                    # Act
                    response = test_client.post("/collect/start")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "status" in data
        assert "message" in data

    def test_start_collection_already_running(self, test_client):
        """
        WHY: Prevent starting multiple concurrent collections.
        ARRANGE: Collection already running
        ACT: POST to /collect/start
        ASSERT: Returns 400 error
        """
        # Arrange
        with patch('app.main.collection_manager._is_running', True):
            with patch('app.main.collection_manager._status', CollectionStatusEnum.ONGOING):
                # Act
                response = test_client.post("/collect/start")

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already running" in response.json()["detail"]

    def test_stop_collection_success(self, test_client):
        """
        WHY: Users need to manually stop collection.
        ARRANGE: Collection is running
        ACT: POST to /collect/stop
        ASSERT: Returns 200 with updated status
        """
        # Arrange
        from app.models import CollectionStatusResponse

        with patch('app.main.collection_manager._is_running', True):
            with patch('app.main.collection_manager.stop') as mock_stop:
                with patch('app.main.collection_manager.get_status') as mock_status:
                    # Return a proper response object with all required fields
                    mock_status.return_value = CollectionStatusResponse(
                        task_id=1,
                        status=CollectionStatusEnum.FINISHED,
                        message="Collection stopped",
                        datapoints_collected=10,
                        start_time=None,
                        stop_time=None,
                        scheduler_running=None,
                        scheduled_times=None
                    )

                    # Act
                    response = test_client.post("/collect/stop")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "FINISHED"

    def test_stop_collection_not_running(self, test_client):
        """
        WHY: Stopping a non-running collection should return error.
        ARRANGE: No collection running
        ACT: POST to /collect/stop
        ASSERT: Returns 400 error
        """
        # Arrange
        with patch('app.main.collection_manager._is_running', False):
            # Act
            response = test_client.post("/collect/stop")

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "not currently running" in response.json()["detail"]

    def test_get_collection_status(self, test_client):
        """
        WHY: Users need to check current collection status.
        ARRANGE: Collection in progress
        ACT: GET /collect/status
        ASSERT: Returns current status with scheduler info
        """
        # Arrange
        from app.models import CollectionStatusResponse

        with patch('app.main.collection_manager.get_status') as mock_status:
            mock_status.return_value = CollectionStatusResponse(
                task_id=1,
                status=CollectionStatusEnum.ONGOING,
                message="Collection in progress",
                start_time=datetime.now(ZoneInfo("America/Bogota")),
                datapoints_collected=5,
                stop_time=None,
                scheduler_running=None,
                scheduled_times=None
            )
            with patch('app.main.scheduler.is_running', True):
                # Act
                response = test_client.get("/collect/status")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "status" in data
        assert "scheduler_running" in data
        assert "scheduled_times" in data


class TestSchedulerEndpoints:
    """Tests for /scheduler/* endpoints."""

    def test_start_scheduler(self, test_client):
        """
        WHY: Users can manually control the scheduler.
        ARRANGE: Scheduler not running
        ACT: POST to /scheduler/start
        ASSERT: Returns success message
        """
        # Arrange
        with patch('app.main.scheduler.start_scheduler') as mock_start:
            # Act
            response = test_client.post("/scheduler/start")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert "started" in response.json()["message"]

    def test_stop_scheduler(self, test_client):
        """
        WHY: Users can stop automatic scheduling.
        ARRANGE: Scheduler running
        ACT: POST to /scheduler/stop
        ASSERT: Returns success message
        """
        # Arrange
        with patch('app.main.scheduler.stop_scheduler') as mock_stop:
            # Act
            response = test_client.post("/scheduler/stop")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert "stopped" in response.json()["message"]

    def test_get_scheduler_status(self, test_client):
        """
        WHY: Users need to see scheduler configuration.
        ARRANGE: Scheduler in known state
        ACT: GET /scheduler/status
        ASSERT: Returns scheduler info
        """
        # Arrange
        with patch('app.main.scheduler.is_running', True):
            with patch('app.main.collection_manager._is_running', False):
                # Act
                response = test_client.get("/scheduler/status")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "scheduler_running" in data
        assert "collection_running" in data
        assert "timezone" in data
        assert data["timezone"] == "America/Bogota"


class TestFetchRemoteDataEndpoint:
    """Tests for /fetch-remote-data endpoint."""

    def test_fetch_remote_data_success(self, test_client, mock_scraper_credentials):
        """
        WHY: Manual data fetch for testing/debugging.
        ARRANGE: Mock successful scraper response
        ACT: POST to /fetch-remote-data
        ASSERT: Returns ScrapingResponse data
        """
        # Arrange
        mock_response = ScrapingResponse(
            source="rutasljrj.net",
            valores_data=[["101", "Ruta", "4.6", "-74.0", "img.png", "2025-01-15 08:30:00"]],
            estados_data=[["1", "En recorrido", "2025-01-15 08:30:00", "439", "S", "Subio", "2025-01-15 08:35:00"]]
        )

        with patch('app.main.collection_manager._fetch_remote_data_async') as mock_fetch:
            mock_fetch.return_value = mock_response

            # Act
            response = test_client.post("/fetch-remote-data")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert data["data"]["source"] == "rutasljrj.net"
        assert len(data["data"]["valores_data"]) > 0

    def test_fetch_remote_data_failure(self, test_client, mock_scraper_credentials):
        """
        WHY: External API failures should be handled gracefully.
        ARRANGE: Mock scraper error
        ACT: POST to /fetch-remote-data
        ASSERT: Returns 500 error with message
        """
        # Arrange
        with patch('app.main.collection_manager._fetch_remote_data_async') as mock_fetch:
            mock_fetch.side_effect = Exception("Network error")

            # Act
            response = test_client.post("/fetch-remote-data")

        # Assert
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Failed to fetch data" in response.json()["detail"]


# =============================================================================
# DATA SERVER ENDPOINT TESTS (data_server.py)
# =============================================================================

class TestDataServerEndpoints:
    """Tests for /data/* endpoints."""

    def test_get_session_datapoints_success(self, test_client, db_session, bogota_time):
        """
        WHY: Retrieve all datapoints for a specific collection session.
        ARRANGE: Session with datapoints in database
        ACT: GET /data/sessions/{session_id}/datapoints
        ASSERT: Returns session metadata and datapoints
        """
        # Arrange - Create collection session
        session = CollectionMetadata(
            start_time=bogota_time,
            stop_time=bogota_time + timedelta(hours=1),
            status=CollectionStatusEnum.FINISHED.value,
            datapoints_count=2,
            last_update_time=bogota_time
        )
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        # Add datapoints
        entry1 = RouteDataEntry(
            ruta=101,
            ns_latitude=4.6097,
            ew_longitude=-74.0817,
            route_status="En recorrido",
            student_status="Subio",
            collected_at=bogota_time + timedelta(minutes=10)
        )
        entry2 = RouteDataEntry(
            ruta=101,
            ns_latitude=4.6100,
            ew_longitude=-74.0820,
            route_status="En recorrido",
            student_status="Subio",
            collected_at=bogota_time + timedelta(minutes=20)
        )
        db_session.add(entry1)
        db_session.add(entry2)
        db_session.commit()

        # Act
        response = test_client.get(f"/data/sessions/{session.id}/datapoints")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "collection" in data
        assert "datapoints" in data
        assert data["collection"]["id"] == session.id
        assert len(data["datapoints"]) == 2

    def test_get_session_datapoints_not_found(self, test_client):
        """
        WHY: Invalid session IDs should return 404.
        ARRANGE: No session with ID 999
        ACT: GET /data/sessions/999/datapoints
        ASSERT: Returns 404 error
        """
        # Act
        response = test_client.get("/data/sessions/999/datapoints")

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"]

    def test_get_session_datapoints_ongoing_uses_current_time(self, test_client, db_session, bogota_time):
        """
        WHY: Ongoing sessions (stop_time = null) should use current time.
        ARRANGE: Session without stop_time
        ACT: GET /data/sessions/{session_id}/datapoints
        ASSERT: Returns datapoints up to current time
        """
        # Arrange
        # Create session that started in the past
        session_start = bogota_time - timedelta(hours=1)
        session = CollectionMetadata(
            start_time=session_start,
            stop_time=None,  # Ongoing
            status=CollectionStatusEnum.ONGOING.value,
            datapoints_count=1,
            last_update_time=session_start
        )
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        # Add datapoint from 30 minutes ago (should be found)
        entry = RouteDataEntry(
            ruta=101,
            ns_latitude=4.6097,
            ew_longitude=-74.0817,
            route_status="En recorrido",
            student_status="Subio",
            collected_at=bogota_time - timedelta(minutes=30)
        )
        db_session.add(entry)
        db_session.commit()

        # Act
        response = test_client.get(f"/data/sessions/{session.id}/datapoints")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["datapoints"]) == 1

    def test_datapoints_by_range_success(self, test_client, db_session, bogota_time):
        """
        WHY: Query datapoints within a specific time range.
        ARRANGE: Multiple datapoints across time
        ACT: POST /data/datapoints/range with time range
        ASSERT: Returns only datapoints in range
        """
        # Arrange - Create datapoints at different times
        entry1 = RouteDataEntry(
            ruta=101,
            ns_latitude=4.6097,
            ew_longitude=-74.0817,
            route_status="En recorrido",
            student_status="Subio",
            collected_at=bogota_time + timedelta(minutes=5)
        )
        entry2 = RouteDataEntry(
            ruta=101,
            ns_latitude=4.6100,
            ew_longitude=-74.0820,
            route_status="En recorrido",
            student_status="Subio",
            collected_at=bogota_time + timedelta(minutes=15)
        )
        entry3 = RouteDataEntry(
            ruta=101,
            ns_latitude=4.6105,
            ew_longitude=-74.0825,
            route_status="En recorrido",
            student_status="Subio",
            collected_at=bogota_time + timedelta(minutes=25)
        )
        db_session.add_all([entry1, entry2, entry3])
        db_session.commit()

        # Act - Query for middle entry only
        payload = {
            "start": (bogota_time + timedelta(minutes=10)).isoformat(),
            "stop": (bogota_time + timedelta(minutes=20)).isoformat()
        }
        response = test_client.post("/data/datapoints/range", json=payload)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["ns_latitude"] == 4.6100  # Only entry2

    def test_datapoints_by_range_invalid_range(self, test_client, bogota_time):
        """
        WHY: start > stop should be rejected.
        ARRANGE: Invalid time range (start after stop)
        ACT: POST /data/datapoints/range
        ASSERT: Returns 400 error
        """
        # Arrange
        payload = {
            "start": (bogota_time + timedelta(hours=2)).isoformat(),
            "stop": bogota_time.isoformat()  # stop before start!
        }

        # Act
        response = test_client.post("/data/datapoints/range", json=payload)

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "start must be <= stop" in response.json()["detail"]

    def test_datapoints_by_range_empty_result(self, test_client, bogota_time):
        """
        WHY: No matching datapoints should return empty array.
        ARRANGE: No datapoints in database
        ACT: POST /data/datapoints/range
        ASSERT: Returns empty list
        """
        # Arrange
        payload = {
            "start": bogota_time.isoformat(),
            "stop": (bogota_time + timedelta(hours=1)).isoformat()
        }

        # Act
        response = test_client.post("/data/datapoints/range", json=payload)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================

class TestErrorHandling:
    """Tests for error handling across endpoints."""

    def test_invalid_json_returns_422(self, test_client):
        """
        WHY: Malformed JSON should be rejected by FastAPI.
        ARRANGE: Invalid JSON payload
        ACT: POST with bad JSON
        ASSERT: Returns 422 validation error
        """
        # Act
        response = test_client.post(
            "/data/datapoints/range",
            data="not valid json",
            headers={"Content-Type": "application/json"}
        )

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_missing_required_fields_returns_422(self, test_client):
        """
        WHY: Pydantic validation should enforce required fields.
        ARRANGE: Payload missing required field
        ACT: POST /data/datapoints/range
        ASSERT: Returns 422 validation error
        """
        # Arrange - missing 'stop' field
        payload = {
            "start": datetime.now(ZoneInfo("America/Bogota")).isoformat()
        }

        # Act
        response = test_client.post("/data/datapoints/range", json=payload)

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# =============================================================================
# ASYNC CLIENT TESTS (for endpoints that truly need async)
# =============================================================================

class TestAsyncEndpoints:
    """Tests using AsyncClient for async endpoints."""

    @pytest.mark.asyncio
    async def test_start_collection_async(self, async_test_client, mock_scraper_credentials):
        """
        WHY: Demonstrates testing async endpoints.
        ARRANGE: Mock async collection manager
        ACT: POST to /collect/start using async client
        ASSERT: Works with async/await
        """
        # Arrange
        from app.models import CollectionStatusResponse

        with patch('app.main.collection_manager.start') as mock_start:
            mock_start.return_value = True
            with patch('app.main.collection_manager._is_running', False):
                with patch('app.main.collection_manager.get_status') as mock_status:
                    mock_status.return_value = CollectionStatusResponse(
                        task_id=1,
                        status=CollectionStatusEnum.IDLE,
                        message="Started",
                        datapoints_collected=0,
                        start_time=None,
                        stop_time=None,
                        scheduler_running=None,
                        scheduled_times=None
                    )

                    # Act
                    response = await async_test_client.post("/collect/start")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "status" in data


# =============================================================================
# SESSION MANAGEMENT ENDPOINT TESTS (main.py)
# =============================================================================

class TestSetSessionCookiesEndpoint:
    """Tests for POST /session/set-cookies."""

    def test_set_cookies_success(self, test_client):
        payload = {"cf_clearance": "cf_abc", "ci_session": "ci_xyz"}
        response = test_client.post("/session/set-cookies", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Cookies set successfully"
        assert set(data["cookies_set"]) == {"cf_clearance", "ci_session"}
        assert data["cookies_count"] == 2

    def test_set_cookies_empty_payload_returns_400(self, test_client):
        response = test_client.post("/session/set-cookies", json={})
        assert response.status_code == 400

    def test_set_cookies_stores_on_collection_manager(self, test_client):
        from app.scraper_async import collection_manager
        payload = {"cf_clearance": "cf_test", "ci_session": "ci_test"}
        test_client.post("/session/set-cookies", json=payload)
        assert collection_manager._session_cookies == payload
        assert collection_manager._last_login_time is not None


class TestGetSessionStatusEndpoint:
    """Tests for GET /session/status."""

    def test_status_no_session(self, test_client):
        from app.scraper_async import collection_manager
        collection_manager._last_login_time = None
        collection_manager._session_cookies = None

        response = test_client.get("/session/status")
        assert response.status_code == 200
        assert response.json()["status"] == "no_session"

    def test_status_valid_session(self, test_client):
        from app.scraper_async import collection_manager
        from datetime import datetime
        from zoneinfo import ZoneInfo
        collection_manager._last_login_time = datetime.now(ZoneInfo("America/Bogota"))
        collection_manager._session_cookies = {"cf_clearance": "cf", "ci_session": "ci"}

        response = test_client.get("/session/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "valid"
        assert data["expires_in_seconds"] > 0

    def test_status_expired_session_includes_refresh_instructions(self, test_client):
        from app.scraper_async import collection_manager
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo
        collection_manager._last_login_time = (
            datetime.now(ZoneInfo("America/Bogota")) - timedelta(hours=3)
        )
        collection_manager._session_cookies = {"cf_clearance": "cf", "ci_session": "ci"}

        response = test_client.get("/session/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "expired"
        assert "refresh_instructions" in data


class TestTriggerCookieRefreshEndpoint:
    """Tests for POST /session/refresh."""

    def test_refresh_success_returns_200(self, test_client):
        with patch("app.main.run_refresh", new=AsyncMock(return_value=True)):
            response = test_client.post("/session/refresh")
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_refresh_failure_returns_500(self, test_client):
        with patch("app.main.run_refresh", new=AsyncMock(return_value=False)):
            response = test_client.post("/session/refresh")
        assert response.status_code == 500

    def test_refresh_unexpected_exception_returns_500(self, test_client):
        with patch("app.main.run_refresh", new=AsyncMock(side_effect=RuntimeError("boom"))):
            response = test_client.post("/session/refresh")
        assert response.status_code == 500
        assert "boom" in response.json()["detail"]


class TestHealthEndpoint:
    def test_health_returns_ok(self, test_client):
        response = test_client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
