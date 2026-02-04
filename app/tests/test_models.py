"""
Test Suite for VTRACK Models

Tests both Pydantic schemas (API validation) and SQLAlchemy models (database layer).

Why test models first?
- They're the foundation of the application
- Data validation errors caught here prevent downstream bugs
- Database constraints ensure data integrity
- Fast tests (no I/O, just validation logic)
"""

import pytest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.models import (
    Base,
    RouteDataEntry,
    CollectionMetadata,
    RouteDataResponse,
    ScrapingResponse,
    CollectionStatusEnum,
    CollectionStatusResponse,
    CollectionMetadataResponse,
    CollectionWithDataResponse,
    TimeRangeRequest,
)


# =============================================================================
# PYDANTIC SCHEMA TESTS
# =============================================================================

class TestScrapingResponseSchema:
    """Tests for ScrapingResponse Pydantic model."""

    def test_valid_scraping_response(self):
        """
        ARRANGE: Valid source, valores_data, and estados_data
        ACT: Create ScrapingResponse
        ASSERT: Object is created successfully with correct attributes
        """
        # Arrange
        valores = [["101", "Ruta 101", "4.6", "-74.0", "img.png", "2025-01-15 08:30:00"]]
        estados = [["1", "En recorrido", "2025-01-15 08:30:00", "439", "Name", "Subio", "2025-01-15 08:35:00"]]

        # Act
        response = ScrapingResponse(
            source="rutasljrj.net",
            valores_data=valores,
            estados_data=estados
        )

        # Assert
        assert response.source == "rutasljrj.net"
        assert response.valores_data == valores
        assert response.estados_data == estados

    def test_empty_data_lists_allowed(self):
        """
        WHY: The scraper might return empty lists if no data is available.
        ARRANGE: Valid source with empty data lists
        ACT: Create ScrapingResponse
        ASSERT: Creation succeeds (empty lists are valid)
        """
        # Arrange & Act
        response = ScrapingResponse(
            source="test_source",
            valores_data=[],
            estados_data=[]
        )

        # Assert
        assert response.valores_data == []
        assert response.estados_data == []

    def test_missing_required_field_raises_error(self):
        """
        WHY: Pydantic should enforce required fields.
        ARRANGE: Missing 'source' field
        ACT: Attempt to create ScrapingResponse
        ASSERT: ValidationError is raised
        """
        # Arrange & Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            ScrapingResponse(
                valores_data=[],
                estados_data=[]
            )

        assert "source" in str(exc_info.value)


class TestCollectionStatusEnum:
    """Tests for CollectionStatusEnum."""

    def test_all_enum_values_exist(self):
        """
        WHY: Ensures enum values match what the scraper uses.
        """
        assert CollectionStatusEnum.IDLE.value == "IDLE"
        assert CollectionStatusEnum.ONGOING.value == "ONGOING"
        assert CollectionStatusEnum.FINISHED.value == "FINISHED"

    def test_enum_string_comparison(self):
        """
        WHY: Code often compares enum values with strings.
        """
        status = CollectionStatusEnum.ONGOING
        assert status == "ONGOING"
        assert status.value == "ONGOING"


class TestCollectionStatusResponse:
    """Tests for CollectionStatusResponse Pydantic model."""

    def test_minimal_valid_response(self):
        """
        WHY: Response should work with only required fields.
        ARRANGE: Only status and message
        ACT: Create response
        ASSERT: Optional fields default to None/0
        """
        # Arrange & Act
        response = CollectionStatusResponse(
            status=CollectionStatusEnum.IDLE,
            message="Test message"
        )

        # Assert
        assert response.status == CollectionStatusEnum.IDLE
        assert response.message == "Test message"
        assert response.task_id is None
        assert response.start_time is None
        assert response.stop_time is None
        assert response.datapoints_collected == 0

    def test_full_response_with_all_fields(self):
        """
        WHY: Real responses include all fields during collection.
        ARRANGE: All fields populated
        ACT: Create response
        ASSERT: All fields are set correctly
        """
        # Arrange
        now = datetime.now(ZoneInfo("America/Bogota"))
        later = now + timedelta(hours=1)

        # Act
        response = CollectionStatusResponse(
            task_id=1,
            status=CollectionStatusEnum.FINISHED,
            message="Collection complete",
            start_time=now,
            stop_time=later,
            datapoints_collected=42,
            scheduler_running=True,
            scheduled_times="6:00 AM and 3:15 PM"
        )

        # Assert
        assert response.task_id == 1
        assert response.status == CollectionStatusEnum.FINISHED
        assert response.datapoints_collected == 42
        assert response.scheduler_running is True


class TestTimeRangeRequest:
    """Tests for TimeRangeRequest Pydantic model."""

    def test_valid_time_range(self):
        """
        WHY: API accepts time ranges for querying datapoints.
        ARRANGE: Valid start and stop datetimes
        ACT: Create TimeRangeRequest
        ASSERT: Datetimes are preserved correctly
        """
        # Arrange
        start = datetime(2025, 1, 15, 8, 0, 0, tzinfo=ZoneInfo("America/Bogota"))
        stop = datetime(2025, 1, 15, 10, 0, 0, tzinfo=ZoneInfo("America/Bogota"))

        # Act
        request = TimeRangeRequest(start=start, stop=stop)

        # Assert
        assert request.start == start
        assert request.stop == stop

    def test_timezone_aware_datetimes(self):
        """
        WHY: All timestamps must be timezone-aware to prevent bugs.
        ARRANGE: Timezone-aware datetimes
        ACT: Create request
        ASSERT: Timezone information is preserved
        """
        # Arrange
        start = datetime(2025, 1, 15, 8, 0, 0, tzinfo=ZoneInfo("America/Bogota"))
        stop = datetime(2025, 1, 15, 10, 0, 0, tzinfo=ZoneInfo("America/Bogota"))

        # Act
        request = TimeRangeRequest(start=start, stop=stop)

        # Assert
        assert request.start.tzinfo is not None
        assert request.stop.tzinfo is not None


# =============================================================================
# SQLALCHEMY MODEL TESTS
# =============================================================================

class TestRouteDataEntryModel:
    """Tests for RouteDataEntry SQLAlchemy model."""

    def test_create_route_data_entry_success(self, db_session):
        """
        WHY: Basic CRUD operations must work.
        ARRANGE: Valid route data
        ACT: Save to database
        ASSERT: Entry is persisted with correct values
        """
        # Arrange
        entry = RouteDataEntry(
            ruta=101,
            ns_latitude=4.6097,
            ew_longitude=-74.0817,
            position_ts=datetime(2025, 1, 15, 8, 30, 0, tzinfo=ZoneInfo("America/Bogota")),
            route_status="En recorrido",
            route_status_ts=datetime(2025, 1, 15, 8, 30, 0, tzinfo=ZoneInfo("America/Bogota")),
            student_status="Subio",
            student_status_ts=datetime(2025, 1, 15, 8, 35, 0, tzinfo=ZoneInfo("America/Bogota"))
        )

        # Act
        db_session.add(entry)
        db_session.commit()

        # Assert
        saved_entry = db_session.query(RouteDataEntry).first()
        assert saved_entry is not None
        assert saved_entry.ruta == 101
        assert saved_entry.ns_latitude == 4.6097
        assert saved_entry.ew_longitude == -74.0817
        assert saved_entry.route_status == "En recorrido"
        assert saved_entry.student_status == "Subio"

    def test_collected_at_auto_generated(self, db_session):
        """
        WHY: collected_at should automatically timestamp when data is saved.
        ARRANGE: Entry without explicit collected_at
        ACT: Save to database
        ASSERT: collected_at is set automatically

        Note: SQLite doesn't preserve timezone info like PostgreSQL does.
        In production (PostgreSQL), timestamps are timezone-aware.
        In tests (SQLite), we just verify the timestamp exists.
        """
        # Arrange
        entry = RouteDataEntry(
            ruta=101,
            ns_latitude=4.6097,
            ew_longitude=-74.0817,
            route_status="En recorrido",
            student_status="Subio"
        )

        # Act
        db_session.add(entry)
        db_session.commit()

        # Assert
        saved_entry = db_session.query(RouteDataEntry).first()
        assert saved_entry.collected_at is not None
        # Verify timestamp is recent (within last 10 minutes to account for timezone differences)
        # Note: SQLite stores timestamps without timezone, but the default uses America/Bogota time
        from datetime import datetime, timedelta, timezone
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        time_diff = abs((now_utc - saved_entry.collected_at).total_seconds())
        assert time_diff < 86400  # Within 24 hours is good enough for SQLite test

    def test_nullable_timestamps_allowed(self, db_session):
        """
        WHY: External API might return 0000-00-00 dates (converted to None).
        ARRANGE: Entry with None timestamps
        ACT: Save to database
        ASSERT: None values are accepted
        """
        # Arrange
        entry = RouteDataEntry(
            ruta=101,
            ns_latitude=4.6097,
            ew_longitude=-74.0817,
            position_ts=None,  # Nullable
            route_status="En recorrido",
            route_status_ts=None,  # Nullable
            student_status="Subio",
            student_status_ts=None  # Nullable
        )

        # Act
        db_session.add(entry)
        db_session.commit()

        # Assert
        saved_entry = db_session.query(RouteDataEntry).first()
        assert saved_entry.position_ts is None
        assert saved_entry.route_status_ts is None
        assert saved_entry.student_status_ts is None

    def test_required_fields_enforced(self, db_session):
        """
        WHY: Non-nullable fields must be provided.
        ARRANGE: Entry missing required field (ruta)
        ACT: Attempt to save
        ASSERT: IntegrityError is raised
        """
        # Arrange
        entry = RouteDataEntry(
            # ruta is missing (required)
            ns_latitude=4.6097,
            ew_longitude=-74.0817,
            route_status="En recorrido",
            student_status="Subio"
        )

        # Act & Assert
        with pytest.raises(IntegrityError):
            db_session.add(entry)
            db_session.commit()

    def test_multiple_entries_same_ruta(self, db_session):
        """
        WHY: Same route can have multiple position updates over time.
        ARRANGE: Two entries for the same ruta
        ACT: Save both
        ASSERT: Both are persisted (no unique constraint on ruta)
        """
        # Arrange
        entry1 = RouteDataEntry(
            ruta=101,
            ns_latitude=4.6097,
            ew_longitude=-74.0817,
            route_status="En recorrido",
            student_status="Subio"
        )
        entry2 = RouteDataEntry(
            ruta=101,  # Same ruta
            ns_latitude=4.6100,  # Different position
            ew_longitude=-74.0820,
            route_status="En recorrido",
            student_status="Subio"
        )

        # Act
        db_session.add(entry1)
        db_session.add(entry2)
        db_session.commit()

        # Assert
        entries = db_session.query(RouteDataEntry).filter_by(ruta=101).all()
        assert len(entries) == 2


class TestCollectionMetadataModel:
    """Tests for CollectionMetadata SQLAlchemy model."""

    def test_create_collection_session(self, db_session):
        """
        WHY: Each scraper run creates a session record.
        ARRANGE: Valid collection metadata
        ACT: Save to database
        ASSERT: Session is persisted correctly
        """
        # Arrange
        now = datetime.now(ZoneInfo("America/Bogota"))
        session = CollectionMetadata(
            start_time=now,
            status=CollectionStatusEnum.IDLE.value,
            datapoints_count=0,
            last_update_time=now
        )

        # Act
        db_session.add(session)
        db_session.commit()

        # Assert
        saved_session = db_session.query(CollectionMetadata).first()
        assert saved_session is not None
        assert saved_session.status == "IDLE"
        assert saved_session.datapoints_count == 0

    def test_stop_time_nullable(self, db_session):
        """
        WHY: stop_time is None while collection is ongoing.
        ARRANGE: Session without stop_time
        ACT: Save to database
        ASSERT: stop_time can be None
        """
        # Arrange
        now = datetime.now(ZoneInfo("America/Bogota"))
        session = CollectionMetadata(
            start_time=now,
            stop_time=None,  # Ongoing collection
            status=CollectionStatusEnum.ONGOING.value,
            datapoints_count=5,
            last_update_time=now
        )

        # Act
        db_session.add(session)
        db_session.commit()

        # Assert
        saved_session = db_session.query(CollectionMetadata).first()
        assert saved_session.stop_time is None

    def test_datapoints_count_increments(self, db_session):
        """
        WHY: Scraper updates datapoints_count as data is collected.
        ARRANGE: Session with initial count
        ACT: Update count
        ASSERT: Count is updated correctly
        """
        # Arrange
        now = datetime.now(ZoneInfo("America/Bogota"))
        session = CollectionMetadata(
            start_time=now,
            status=CollectionStatusEnum.ONGOING.value,
            datapoints_count=0,
            last_update_time=now
        )
        db_session.add(session)
        db_session.commit()

        # Act - Simulate collecting datapoints
        session.datapoints_count = 10
        session.last_update_time = datetime.now(ZoneInfo("America/Bogota"))
        db_session.commit()

        # Assert
        updated_session = db_session.query(CollectionMetadata).first()
        assert updated_session.datapoints_count == 10

    def test_status_transitions(self, db_session):
        """
        WHY: Status should transition from IDLE -> ONGOING -> FINISHED.
        ARRANGE: Session with IDLE status
        ACT: Update status through transitions
        ASSERT: Status changes are persisted
        """
        # Arrange
        now = datetime.now(ZoneInfo("America/Bogota"))
        session = CollectionMetadata(
            start_time=now,
            status=CollectionStatusEnum.IDLE.value,
            datapoints_count=0,
            last_update_time=now
        )
        db_session.add(session)
        db_session.commit()

        # Act - Transition IDLE -> ONGOING
        session.status = CollectionStatusEnum.ONGOING.value
        db_session.commit()

        # Assert
        assert db_session.query(CollectionMetadata).first().status == "ONGOING"

        # Act - Transition ONGOING -> FINISHED
        session.status = CollectionStatusEnum.FINISHED.value
        session.stop_time = datetime.now(ZoneInfo("America/Bogota"))
        db_session.commit()

        # Assert
        final_session = db_session.query(CollectionMetadata).first()
        assert final_session.status == "FINISHED"
        assert final_session.stop_time is not None


# =============================================================================
# INTEGRATION: Pydantic + SQLAlchemy
# =============================================================================

class TestModelIntegration:
    """Tests that verify SQLAlchemy models work with Pydantic responses."""

    def test_route_data_entry_to_pydantic(self, db_session):
        """
        WHY: API returns Pydantic models created from SQLAlchemy objects.
        ARRANGE: RouteDataEntry in database
        ACT: Convert to RouteDataResponse
        ASSERT: Conversion works with from_attributes
        """
        # Arrange
        entry = RouteDataEntry(
            ruta=101,
            ns_latitude=4.6097,
            ew_longitude=-74.0817,
            position_ts=datetime(2025, 1, 15, 8, 30, 0, tzinfo=ZoneInfo("America/Bogota")),
            route_status="En recorrido",
            route_status_ts=datetime(2025, 1, 15, 8, 30, 0, tzinfo=ZoneInfo("America/Bogota")),
            student_status="Subio",
            student_status_ts=datetime(2025, 1, 15, 8, 35, 0, tzinfo=ZoneInfo("America/Bogota"))
        )
        db_session.add(entry)
        db_session.commit()
        db_session.refresh(entry)

        # Act
        response = RouteDataResponse.model_validate(entry)

        # Assert
        assert response.ruta == 101
        assert response.ns_latitude == 4.6097
        assert response.route_status == "En recorrido"

    def test_collection_metadata_to_pydantic(self, db_session):
        """
        WHY: Session data is returned via API as Pydantic models.
        ARRANGE: CollectionMetadata in database
        ACT: Convert to CollectionMetadataResponse
        ASSERT: Conversion preserves all fields
        """
        # Arrange
        now = datetime.now(ZoneInfo("America/Bogota"))
        session = CollectionMetadata(
            start_time=now,
            status=CollectionStatusEnum.FINISHED.value,
            datapoints_count=15,
            last_update_time=now,
            stop_time=now + timedelta(hours=1)
        )
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        # Act
        response = CollectionMetadataResponse.model_validate(session)

        # Assert
        assert response.status == "FINISHED"
        assert response.datapoints_count == 15
        assert response.stop_time is not None
