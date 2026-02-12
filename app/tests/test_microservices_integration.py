"""
Test Suite for Microservices Integration with Scraper

Tests the integration between:
- AsyncCollectionManager (scraper) 
- MessageQueue (Redis)
- Collected data flow to Redis

TDD Approach:
We test the integration pathway:
1. Collection manager has message queue
2. When data is collected, it's pushed to queue
3. Coordinates can be retrieved from queue
4. Full cycle: collect -> queue -> consume
"""

import pytest
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import AsyncMock, MagicMock

from shared.message_queue import MessageQueue


class TestCollectionManagerRedisIntegration:
    """Tests for integrating AsyncCollectionManager with Redis queue."""

    @pytest.mark.asyncio
    async def test_collection_manager_can_accept_message_queue(self, db_session):
        """
        ARRANGE: AsyncCollectionManager and MessageQueue
        ACT: Assign message queue to collection manager
        ASSERT: Assignment successful
        """
        from app.scraper_async import AsyncCollectionManager
        
        # Arrange
        manager = AsyncCollectionManager()
        # Note: In real tests with fakeredis, we'd pass actual queue
        # For now, just verify the structure
        
        # Act
        queue = MagicMock()
        manager.message_queue = queue
        
        # Assert
        assert manager.message_queue is not None

    @pytest.mark.asyncio
    async def test_scraper_saves_and_queues_coordinate(self, db_session, fake_redis_client):
        """
        ARRANGE: Collection manager with message queue
        ACT: Simulate coordinate collection and queuing
        ASSERT: Data is both saved to DB and queued
        """
        from app.scraper_async import AsyncCollectionManager
        from shared.message_queue import MessageQueue
        
        # Arrange
        manager = AsyncCollectionManager()
        queue = MagicMock()
        queue.push_coordinate = MagicMock(return_value=True)
        manager.message_queue = queue
        
        sample_data = {
            'ruta': 101,
            'ns_latitude': 4.7110,
            'ew_longitude': -74.0059,
            'position_ts': datetime(2025, 1, 15, 8, 30, 0, tzinfo=ZoneInfo("America/Bogota")),
            'route_status': "En recorrido",
            'route_status_ts': datetime(2025, 1, 15, 8, 30, 0, tzinfo=ZoneInfo("America/Bogota")),
            'student_status': "Subio",
            'student_status_ts': datetime(2025, 1, 15, 8, 35, 0, tzinfo=ZoneInfo("America/Bogota")),
        }
        
        # Act
        await manager._save_route_data_async(sample_data)
        
        # Assert
        # Verify DB operation happened
        assert manager.datapoints_collected == 1
        
        # Verify queue method was called
        queue.push_coordinate.assert_called_once()
        call_args = queue.push_coordinate.call_args
        assert call_args[1]['ruta'] == 101
        assert call_args[1]['latitude'] == 4.7110

    @pytest.mark.asyncio
    def test_queue_receives_correct_coordinate_format(self, message_queue_fixture):
        """
        ARRANGE: Coordinate data ready to send
        ACT: Queue the coordinate
        ASSERT: Queue receives properly formatted data
        """
        # Use fixture message queue with fake redis
        queue = message_queue_fixture
        
        # Act
        queue.push_coordinate(
            ruta=101,
            latitude=4.7110,
            longitude=-74.0059,
            position_ts=datetime(2025, 1, 15, 8, 30, 0, tzinfo=ZoneInfo("America/Bogota")),
            route_status="En recorrido",
            student_status="Subio"
        )
        
        # Assert
        queued = queue.pop_coordinate()
        assert queued['ruta'] == 101
        assert queued['latitude'] == 4.7110
        assert queued['longitude'] == -74.0059
        assert queued['route_status'] == "En recorrido"


class TestCoordinateQueueDataFlow:
    """Tests for data flow through the coordinate queue."""

    def test_coordinate_from_collection_to_archive(self, message_queue_fixture):
        """
        Complete flow: Create coordinate -> Queue -> Retrieve
        """
        # Arrange
        queue = message_queue_fixture
        
        original_data = {
            'ruta': 101,
            'latitude': 4.7110,
            'longitude': -74.0059,
            'position_ts': datetime(2025, 1, 15, 8, 30, 0, tzinfo=ZoneInfo("America/Bogota")),
            'route_status': "En recorrido",
            'student_status': "Subio"
        }
        
        # Act 1: Queue the coordinate
        queue.push_coordinate(**original_data)
        
        # Act 2: Retrieve from queue
        retrieved = queue.pop_coordinate()
        
        # Assert
        assert retrieved is not None
        assert retrieved['ruta'] == original_data['ruta']
        assert retrieved['latitude'] == original_data['latitude']
        assert retrieved['longitude'] == original_data['longitude']
        assert retrieved['route_status'] == original_data['route_status']
        assert retrieved['student_status'] == original_data['student_status']

    def test_multiple_routes_queued_independently(self, message_queue_fixture):
        """
        Different routes queued should be processable independently
        """
        # Arrange
        queue = message_queue_fixture
        
        routes_data = [
            {'ruta': 101, 'latitude': 4.7110, 'longitude': -74.0059},
            {'ruta': 102, 'latitude': 4.6289, 'longitude': -74.0832},
            {'ruta': 103, 'latitude': 4.5500, 'longitude': -74.1000},
        ]
        
        # Act 1: Queue all routes
        for data in routes_data:
            queue.push_coordinate(**data)
        
        # Assert queue length
        assert queue.get_queue_length('coordinate_queue') == 3
        
        # Act 2: Retrieve each route
        retrieved_routes = []
        for _ in range(3):
            coord = queue.pop_coordinate()
            retrieved_routes.append(coord['ruta'])
        
        # Assert - all routes retrieved in order
        assert retrieved_routes == [101, 102, 103]

    def test_coordinate_metadata_preserved_through_queue(self, message_queue_fixture):
        """
        All coordinate metadata should be preserved through queue
        """
        # Arrange
        queue = message_queue_fixture
        
        ts = datetime(2025, 1, 15, 8, 30, 0, tzinfo=ZoneInfo("America/Bogota"))
        
        # Act
        queue.push_coordinate(
            ruta=101,
            latitude=4.7110,
            longitude=-74.0059,
            position_ts=ts,
            route_status="En recorrido",
            student_status="Subio"
        )
        
        retrieved = queue.pop_coordinate()
        
        # Assert - all fields preserved
        assert retrieved['ruta'] == 101
        assert retrieved['latitude'] == 4.7110
        assert retrieved['longitude'] == -74.0059
        assert retrieved['position_ts'] == ts.isoformat()
        assert retrieved['route_status'] == "En recorrido"
        assert retrieved['student_status'] == "Subio"
        assert 'queued_at' in retrieved


class TestAlertQueueIntegration:
    """Tests for alert queue integration with rest of system."""

    def test_queue_alert_from_geofence_analyzer(self, message_queue_fixture, location_analyzer_fixture):
        """
        Alert generated from geofence analyzer should queue properly
        """
        from shared.location_alerts import AlertType
        
        # Arrange
        queue = message_queue_fixture
        
        boyaca_zone = next(
            zone for zone in location_analyzer_fixture.get_zones()
            if zone.name == "Boyaca"
        )
        
        # Generate alert from analyzer
        alerts = location_analyzer_fixture.analyze_coordinate(
            ruta=101,
            latitude=boyaca_zone.latitude,
            longitude=boyaca_zone.longitude
        )
        
        # Act - queue the alert
        for alert in alerts:
            queue.push_alert(
                ruta=alert.ruta,
                latitude=alert.latitude,
                longitude=alert.longitude,
                alert_type=alert.alert_type.value,
                area_name=alert.zone_name,
                severity=alert.severity.value
            )
        
        # Assert
        queued_alert = queue.pop_alert()
        assert queued_alert is not None
        assert queued_alert['ruta'] == 101
        assert queued_alert['alert_type'] == 'GEOFENCE_ENTRY'
        assert queued_alert['area_name'] == 'Boyaca'

    def test_alert_queue_severity_levels(self, message_queue_fixture):
        """
        Different severity levels should queue and retrieve correctly
        """
        # Arrange
        queue = message_queue_fixture
        
        # Act - push alerts with different severities
        severities = ['INFO', 'WARNING', 'CRITICAL']
        for idx, severity in enumerate(severities):
            queue.push_alert(
                ruta=100 + idx,
                latitude=4.7110,
                longitude=-74.0059,
                alert_type='GEOFENCE_ENTRY',
                area_name='Zone',
                severity=severity
            )
        
        # Assert - retrieve and verify
        for expected_severity in severities:
            alert = queue.pop_alert()
            assert alert['severity'] == expected_severity


class TestHighVolumeScenarios:
    """Tests simulating high-volume scenarios."""

    def test_high_volume_coordinate_queueing(self, message_queue_fixture):
        """
        Simulate high volume: 1000 coordinates
        """
        # Arrange
        queue = message_queue_fixture
        
        # Act 1: Push 1000 coordinates
        for i in range(1000):
            queue.push_coordinate(
                ruta=(i % 100) + 1,  # 100 different routes
                latitude=4.7110 + (i * 0.00001),
                longitude=-74.0059
            )
        
        # Assert queue size
        assert queue.get_queue_length('coordinate_queue') == 1000
        
        # Act 2: Pop all and verify
        processed = 0
        while queue.get_queue_length('coordinate_queue') > 0:
            coord = queue.pop_coordinate()
            if coord:
                processed += 1
        
        # Assert
        assert processed == 1000
        assert queue.get_queue_length('coordinate_queue') == 0

    def test_mixed_coordinates_and_alerts_queue(self, message_queue_fixture):
        """
        Both coordinate and alert queues simultaneously
        """
        # Arrange
        queue = message_queue_fixture
        
        # Act 1: Interleave pushing to both queues
        for i in range(100):
            queue.push_coordinate(
                ruta=100 + i,
                latitude=4.7110 + (i * 0.0001),
                longitude=-74.0059
            )
            if i % 5 == 0:
                queue.push_alert(
                    ruta=100 + i,
                    latitude=4.7110 + (i * 0.0001),
                    longitude=-74.0059,
                    alert_type='GEOFENCE_ENTRY',
                    area_name='Zone',
                    severity='INFO'
                )
        
        # Assert
        assert queue.get_queue_length('coordinate_queue') == 100
        assert queue.get_queue_length('alert_queue') == 20  # Every 5th gets alert
        
        # Act 2: Process both independently
        coord_count = 0
        while queue.get_queue_length('coordinate_queue') > 0:
            if queue.pop_coordinate():
                coord_count += 1
        
        alert_count = 0
        while queue.get_queue_length('alert_queue') > 0:
            if queue.pop_alert():
                alert_count += 1
        
        # Assert
        assert coord_count == 100
        assert alert_count == 20


class TestDataConsistency:
    """Tests for data consistency through the pipeline."""

    def test_coordinate_timestamp_consistency(self, message_queue_fixture):
        """
        Timestamp should be preserved and retrievable
        """
        # Arrange
        queue = message_queue_fixture
        
        ts = datetime(2025, 1, 15, 10, 30, 45, tzinfo=ZoneInfo("America/Bogota"))
        
        # Act
        queue.push_coordinate(
            ruta=101,
            latitude=4.7110,
            longitude=-74.0059,
            position_ts=ts
        )
        
        retrieved = queue.pop_coordinate()
        
        # Assert
        assert retrieved['position_ts'] == ts.isoformat()

    def test_queue_fifo_ordering_large_batch(self, message_queue_fixture):
        """
        Large batch should maintain FIFO ordering
        """
        # Arrange
        queue = message_queue_fixture
        
        # Act 1: Push coordinates in order
        rutas = list(range(1, 101))  # Ruta 1-100
        for ruta in rutas:
            queue.push_coordinate(
                ruta=ruta,
                latitude=4.7110,
                longitude=-74.0059
            )
        
        # Act 2: Pop all
        retrieved_rutas = []
        for _ in range(100):
            coord = queue.pop_coordinate()
            if coord:
                retrieved_rutas.append(coord['ruta'])
        
        # Assert FIFO order maintained
        assert retrieved_rutas == rutas


class TestQueueRobustness:
    """Tests for queue robustness and error handling."""

    def test_queue_handles_rapid_push_pop_cycles(self, message_queue_fixture):
        """
        Rapid push-pop cycles should work correctly
        """
        # Arrange
        queue = message_queue_fixture
        
        # Act - rapid cycles
        for cycle in range(10):
            # Push
            for i in range(10):
                queue.push_coordinate(
                    ruta=100 + i,
                    latitude=4.7110,
                    longitude=-74.0059
                )
            
            # Pop immediately
            for i in range(10):
                coord = queue.pop_coordinate()
                assert coord is not None
                assert coord['ruta'] in range(100, 110)
        
        # Assert - queue empty after all cycles
        assert queue.get_queue_length('coordinate_queue') == 0

    def test_queue_recovery_after_empty(self, message_queue_fixture):
        """
        Queue should function normally after being emptied
        """
        # Arrange
        queue = message_queue_fixture
        
        # Act 1: Fill, empty, refill
        for i in range(5):
            queue.push_coordinate(ruta=100 + i, latitude=4.7, longitude=-74.0)
        
        # Empty it
        for _ in range(5):
            queue.pop_coordinate()
        
        assert queue.get_queue_length('coordinate_queue') == 0
        
        # Refill
        for i in range(5):
            queue.push_coordinate(ruta=200 + i, latitude=4.7, longitude=-74.0)
        
        # Assert
        assert queue.get_queue_length('coordinate_queue') == 5
        
        # Verify data
        coord = queue.pop_coordinate()
        assert coord['ruta'] in range(200, 205)
