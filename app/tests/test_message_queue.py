"""
Test Suite for Redis Message Queue

Tests the MessageQueue class for:
- Redis connection and health checks
- Pushing coordinates to the queue
- Popping coordinates from the queue
- Pushing alerts to the queue
- Popping alerts from the queue
- Queue length monitoring

TDD Approach:
We test the public interface of MessageQueue following the functional flow:
1. Initialize and connect
2. Push data
3. Pop data
4. Query queue state
"""

import pytest
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from shared.message_queue import MessageQueue


class TestMessageQueueInitialization:
    """Tests for MessageQueue initialization and connection."""

    def test_message_queue_initializes_successfully(self, redis_url_test, fake_redis_client):
        """
        ARRANGE: Redis client is available
        ACT: Create MessageQueue instance
        ASSERT: MessageQueue is initialized successfully
        """
        # Act
        queue = MessageQueue(redis_url_test)
        
        # Assert
        assert queue is not None
        assert queue.redis_client is not None
        assert queue.redis_url == redis_url_test

    def test_message_queue_health_check_succeeds(self, message_queue_fixture):
        """
        ARRANGE: MessageQueue is initialized
        ACT: Call health_check()
        ASSERT: Returns True indicating Redis is healthy
        """
        # Act
        is_healthy = message_queue_fixture.health_check()
        
        # Assert
        assert is_healthy is True

    def test_message_queue_redis_connection_invalid(self):
        """
        ARRANGE: Invalid Redis URL
        ACT: Try to create MessageQueue with bad URL
        ASSERT: Raises exception during initialization
        """
        # Act & Assert
        with pytest.raises(Exception):
            MessageQueue("redis://invalid-host:99999/0")


class TestCoordinatePushing:
    """Tests for pushing coordinates to the queue."""

    def test_push_coordinate_successfully(self, message_queue_fixture):
        """
        ARRANGE: MessageQueue and coordinate data
        ACT: Push coordinate to queue
        ASSERT: Coordinate is successfully queued and queue length increases
        """
        # Arrange
        ruta = 101
        latitude = 4.7110
        longitude = -74.0059
        
        initial_length = message_queue_fixture.get_queue_length('coordinate_queue')
        
        # Act
        result = message_queue_fixture.push_coordinate(
            ruta=ruta,
            latitude=latitude,
            longitude=longitude
        )
        
        # Assert
        assert result is True
        new_length = message_queue_fixture.get_queue_length('coordinate_queue')
        assert new_length == initial_length + 1

    def test_push_coordinate_with_all_fields(self, message_queue_fixture):
        """
        ARRANGE: Coordinate with all optional fields
        ACT: Push complete coordinate data
        ASSERT: All fields are preserved in the queue
        """
        # Arrange
        ruta = 101
        latitude = 4.7110
        longitude = -74.0059
        position_ts = datetime(2025, 1, 15, 8, 30, 0, tzinfo=ZoneInfo("America/Bogota"))
        route_status = "En recorrido"
        student_status = "Subio"
        
        # Act
        message_queue_fixture.push_coordinate(
            ruta=ruta,
            latitude=latitude,
            longitude=longitude,
            position_ts=position_ts,
            route_status=route_status,
            student_status=student_status
        )
        
        # Pop and verify
        popped = message_queue_fixture.pop_coordinate()
        
        # Assert
        assert popped is not None
        assert popped['ruta'] == ruta
        assert popped['latitude'] == latitude
        assert popped['longitude'] == longitude
        assert popped['position_ts'] == position_ts.isoformat()
        assert popped['route_status'] == route_status
        assert popped['student_status'] == student_status

    def test_push_coordinate_with_none_optional_fields(self, message_queue_fixture):
        """
        ARRANGE: Coordinate with only required fields
        ACT: Push minimal coordinate data
        ASSERT: Push succeeds and optional fields are None
        """
        # Arrange
        ruta = 101
        latitude = 4.7110
        longitude = -74.0059
        
        # Act
        message_queue_fixture.push_coordinate(
            ruta=ruta,
            latitude=latitude,
            longitude=longitude,
            position_ts=None,
            route_status=None,
            student_status=None
        )
        
        # Pop and verify
        popped = message_queue_fixture.pop_coordinate()
        
        # Assert
        assert popped is not None
        assert popped['ruta'] == ruta
        assert popped['latitude'] == latitude
        assert popped['longitude'] == longitude
        assert popped['position_ts'] is None
        assert popped['route_status'] is None
        assert popped['student_status'] is None

    def test_push_coordinate_with_invalid_ruta(self, message_queue_fixture):
        """
        ARRANGE: Coordinate with non-numeric ruta
        ACT: Push coordinate
        ASSERT: Push handles gracefully (Redis accepts any value)
        
        Note: This tests that MessageQueue doesn't do strict validation
        Validation happens at API layer
        """
        # Act - Redis will accept string ruta
        result = message_queue_fixture.push_coordinate(
            ruta="INVALID",
            latitude=4.7110,
            longitude=-74.0059
        )
        
        # Assert
        assert result is True


class TestCoordinatePopping:
    """Tests for popping coordinates from the queue."""

    def test_pop_coordinate_from_empty_queue(self, message_queue_fixture):
        """
        ARRANGE: Empty coordinate queue
        ACT: Try to pop from queue
        ASSERT: Returns None
        """
        # Arrange - queue is empty
        message_queue_fixture.redis_client.delete('coordinate_queue')
        
        # Act
        result = message_queue_fixture.pop_coordinate()
        
        # Assert
        assert result is None

    def test_pop_coordinate_fifo_order(self, message_queue_fixture):
        """
        ARRANGE: Push multiple coordinates
        ACT: Pop coordinates one by one
        ASSERT: Coordinates are returned in FIFO order
        
        Note: Redis LPUSH pushes to head, RPOP pops from tail = FIFO
        """
        # Arrange
        coords = [
            {'ruta': 101, 'lat': 4.7110},
            {'ruta': 102, 'lat': 4.6289},
            {'ruta': 103, 'lat': 4.5500},
        ]
        
        for coord in coords:
            message_queue_fixture.push_coordinate(
                ruta=coord['ruta'],
                latitude=coord['lat'],
                longitude=-74.0000
            )
        
        # Act & Assert - pop in FIFO order
        popped1 = message_queue_fixture.pop_coordinate()
        assert popped1['ruta'] == 101
        
        popped2 = message_queue_fixture.pop_coordinate()
        assert popped2['ruta'] == 102
        
        popped3 = message_queue_fixture.pop_coordinate()
        assert popped3['ruta'] == 103
        
        # Queue should be empty now
        popped4 = message_queue_fixture.pop_coordinate()
        assert popped4 is None

    def test_pop_coordinate_with_data_integrity(self, message_queue_fixture):
        """
        ARRANGE: Push coordinate with special characters/unicode
        ACT: Pop the coordinate
        ASSERT: Data integrity is maintained
        """
        # Arrange - coordinate with unicode characters in optional fields
        message_queue_fixture.push_coordinate(
            ruta=101,
            latitude=4.7110,
            longitude=-74.0059,
            route_status="En recorrido ñ"
        )
        
        # Act
        popped = message_queue_fixture.pop_coordinate()
        
        # Assert
        assert popped['route_status'] == "En recorrido ñ"


class TestAlertPushing:
    """Tests for pushing alerts to the queue."""

    def test_push_alert_successfully(self, message_queue_fixture):
        """
        ARRANGE: MessageQueue and alert data
        ACT: Push alert to queue
        ASSERT: Alert is successfully queued
        """
        # Arrange
        ruta = 101
        latitude = 4.7110
        longitude = -74.0059
        alert_type = "GEOFENCE_ENTRY"
        area_name = "School Zone"
        severity = "INFO"
        
        initial_length = message_queue_fixture.get_queue_length('alert_queue')
        
        # Act
        result = message_queue_fixture.push_alert(
            ruta=ruta,
            latitude=latitude,
            longitude=longitude,
            alert_type=alert_type,
            area_name=area_name,
            severity=severity
        )
        
        # Assert
        assert result is True
        new_length = message_queue_fixture.get_queue_length('alert_queue')
        assert new_length == initial_length + 1

    def test_push_alert_with_all_fields(self, message_queue_fixture):
        """
        ARRANGE: Alert with all fields
        ACT: Push alert and pop it
        ASSERT: All fields are preserved
        """
        # Arrange
        alert_data = {
            'ruta': 101,
            'latitude': 4.7110,
            'longitude': -74.0059,
            'alert_type': 'GEOFENCE_ENTRY',
            'area_name': 'School Zone',
            'severity': 'WARNING'
        }
        
        # Act
        message_queue_fixture.push_alert(**alert_data)
        popped = message_queue_fixture.pop_alert()
        
        # Assert
        assert popped is not None
        assert popped['ruta'] == alert_data['ruta']
        assert popped['latitude'] == alert_data['latitude']
        assert popped['longitude'] == alert_data['longitude']
        assert popped['alert_type'] == alert_data['alert_type']
        assert popped['area_name'] == alert_data['area_name']
        assert popped['severity'] == alert_data['severity']

    def test_push_alert_default_severity(self, message_queue_fixture):
        """
        ARRANGE: Alert without severity specified
        ACT: Push alert with default severity
        ASSERT: Defaults to "INFO"
        """
        # Act
        message_queue_fixture.push_alert(
            ruta=101,
            latitude=4.7110,
            longitude=-74.0059,
            alert_type="GEOFENCE_ENTRY",
            area_name="School Zone"
            # severity not specified
        )
        
        popped = message_queue_fixture.pop_alert()
        
        # Assert
        assert popped['severity'] == "INFO"

    def test_push_alert_different_severity_levels(self, message_queue_fixture):
        """
        ARRANGE: Alerts with different severity levels
        ACT: Push alerts with INFO, WARNING, CRITICAL
        ASSERT: All severity levels are preserved
        """
        # Arrange
        severities = ["INFO", "WARNING", "CRITICAL"]
        
        for severity in severities:
            message_queue_fixture.push_alert(
                ruta=101,
                latitude=4.7110,
                longitude=-74.0059,
                alert_type="GEOFENCE_ENTRY",
                area_name="Zone",
                severity=severity
            )
        
        # Act & Assert
        for severity in severities:
            popped = message_queue_fixture.pop_alert()
            assert popped['severity'] == severity


class TestAlertPopping:
    """Tests for popping alerts from the queue."""

    def test_pop_alert_from_empty_queue(self, message_queue_fixture):
        """
        ARRANGE: Empty alert queue
        ACT: Try to pop from queue
        ASSERT: Returns None
        """
        # Arrange - queue is empty
        message_queue_fixture.redis_client.delete('alert_queue')
        
        # Act
        result = message_queue_fixture.pop_alert()
        
        # Assert
        assert result is None

    def test_pop_alert_fifo_order(self, message_queue_fixture):
        """
        ARRANGE: Push multiple alerts
        ACT: Pop alerts one by one
        ASSERT: Alerts are returned in FIFO order
        """
        # Arrange
        areas = ["Dangerous Zone", "School", "Depot"]
        
        for area in areas:
            message_queue_fixture.push_alert(
                ruta=101,
                latitude=4.7110,
                longitude=-74.0059,
                alert_type="GEOFENCE_ENTRY",
                area_name=area,
                severity="WARNING"
            )
        
        # Act & Assert
        for expected_area in areas:
            popped = message_queue_fixture.pop_alert()
            assert popped['area_name'] == expected_area


class TestQueueLengthMonitoring:
    """Tests for monitoring queue lengths."""

    def test_get_queue_length_empty(self, message_queue_fixture):
        """
        ARRANGE: Empty queues
        ACT: Get queue lengths
        ASSERT: Both return 0
        """
        # Arrange
        message_queue_fixture.redis_client.delete('coordinate_queue')
        message_queue_fixture.redis_client.delete('alert_queue')
        
        # Act & Assert
        assert message_queue_fixture.get_queue_length('coordinate_queue') == 0
        assert message_queue_fixture.get_queue_length('alert_queue') == 0

    def test_get_queue_length_with_data(self, message_queue_fixture):
        """
        ARRANGE: Push multiple items to both queues
        ACT: Get queue lengths
        ASSERT: Lengths match number of items pushed
        """
        # Arrange - push 3 coordinates
        for i in range(3):
            message_queue_fixture.push_coordinate(
                ruta=100 + i,
                latitude=4.7110,
                longitude=-74.0059
            )
        
        # Push 5 alerts
        for i in range(5):
            message_queue_fixture.push_alert(
                ruta=100 + i,
                latitude=4.7110,
                longitude=-74.0059,
                alert_type="GEOFENCE_ENTRY",
                area_name=f"Zone {i}",
                severity="INFO"
            )
        
        # Act & Assert
        assert message_queue_fixture.get_queue_length('coordinate_queue') == 3
        assert message_queue_fixture.get_queue_length('alert_queue') == 5

    def test_queue_length_decreases_after_pop(self, message_queue_fixture):
        """
        ARRANGE: Push items to queue
        ACT: Pop items one by one
        ASSERT: Queue length decreases with each pop
        """
        # Arrange
        for i in range(3):
            message_queue_fixture.push_coordinate(
                ruta=100 + i,
                latitude=4.7110,
                longitude=-74.0059
            )
        
        # Act & Assert
        assert message_queue_fixture.get_queue_length('coordinate_queue') == 3
        
        message_queue_fixture.pop_coordinate()
        assert message_queue_fixture.get_queue_length('coordinate_queue') == 2
        
        message_queue_fixture.pop_coordinate()
        assert message_queue_fixture.get_queue_length('coordinate_queue') == 1
        
        message_queue_fixture.pop_coordinate()
        assert message_queue_fixture.get_queue_length('coordinate_queue') == 0


class TestQueueIndependence:
    """Tests that coordinate and alert queues are independent."""

    def test_coordinate_and_alert_queues_are_separate(self, message_queue_fixture):
        """
        ARRANGE: Data in both queues
        ACT: Push coordinate and alert
        ASSERT: They don't interfere with each other
        """
        # Act
        message_queue_fixture.push_coordinate(
            ruta=101,
            latitude=4.7110,
            longitude=-74.0059
        )
        
        message_queue_fixture.push_alert(
            ruta=101,
            latitude=4.7110,
            longitude=-74.0059,
            alert_type="GEOFENCE_ENTRY",
            area_name="Zone"
        )
        
        # Assert - both queues have their data
        assert message_queue_fixture.get_queue_length('coordinate_queue') == 1
        assert message_queue_fixture.get_queue_length('alert_queue') == 1
        
        # Pop coordinate
        coord = message_queue_fixture.pop_coordinate()
        assert coord['ruta'] == 101
        
        # Alert queue should be unchanged
        assert message_queue_fixture.get_queue_length('alert_queue') == 1
        
        # Pop alert
        alert = message_queue_fixture.pop_alert()
        assert alert['ruta'] == 101
        
        # Both should be empty now
        assert message_queue_fixture.get_queue_length('coordinate_queue') == 0
        assert message_queue_fixture.get_queue_length('alert_queue') == 0
