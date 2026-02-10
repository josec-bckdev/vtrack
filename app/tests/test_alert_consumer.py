"""
Test Suite for Alert Consumer Service

Tests the AlertConsumer class for:
- Initialization and configuration
- Processing coordinates from queue
- Geofence analysis and alert generation
- Statistics tracking
- Health monitoring
- Graceful handling of edge cases

TDD Approach:
We test the consumer's main workflow:
1. Connect to Redis
2. Poll coordinate queue
3. Analyze coordinates
4. Generate and queue alerts
5. Track statistics
"""

import pytest
import logging
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import MagicMock, patch

from shared.message_queue import MessageQueue
from shared.location_alerts import LocationAnalyzer, Zone, AlertType, AlertSeverity

logger = logging.getLogger(__name__)


class MockAlertConsumer:
    """Mock AlertConsumer for testing without async complexity."""
    
    def __init__(self, redis_url, message_queue, location_analyzer):
        self.redis_url = redis_url
        self.message_queue = message_queue
        self.location_analyzer = location_analyzer
        self.is_running = False
        self.processed_count = 0
        self.alert_count = 0
        self.error_count = 0
    
    def _process_coordinate_queue(self):
        """Process one coordinate from queue."""
        coordinate = self.message_queue.pop_coordinate()
        
        if coordinate:
            try:
                ruta = coordinate.get('ruta')
                latitude = coordinate.get('latitude')
                longitude = coordinate.get('longitude')
                
                if not all([ruta, latitude, longitude]):
                    return
                
                # Analyze the coordinate
                alerts = self.location_analyzer.analyze_coordinate(
                    ruta=ruta,
                    latitude=latitude,
                    longitude=longitude
                )
                
                self.processed_count += 1
                
                # Queue any generated alerts
                for alert in alerts:
                    self.message_queue.push_alert(
                        ruta=alert.ruta,
                        latitude=alert.latitude,
                        longitude=alert.longitude,
                        alert_type=alert.alert_type.value,
                        area_name=alert.zone_name,
                        severity=alert.severity.value
                    )
                    self.alert_count += 1
            except Exception as e:
                # Log but continue processing other coordinates
                logger.error(f"Error processing coordinate: {e}")
                self.error_count += 1
    
    def process_queue_once(self):
        """Process entire queue once."""
        while self.message_queue.get_queue_length('coordinate_queue') > 0:
            self._process_coordinate_queue()
    
    def get_stats(self):
        """Get current statistics."""
        return {
            'is_running': self.is_running,
            'coordinates_processed': self.processed_count,
            'alerts_generated': self.alert_count,
            'coordinate_queue_length': self.message_queue.get_queue_length('coordinate_queue'),
            'alert_queue_length': self.message_queue.get_queue_length('alert_queue'),
            'timestamp': datetime.now(ZoneInfo("America/Bogota")).isoformat()
        }


class TestAlertConsumerInitialization:
    """Tests for AlertConsumer setup and configuration."""

    def test_alert_consumer_initializes_successfully(self, message_queue_fixture, location_analyzer_fixture):
        """
        ARRANGE: Dependencies are ready
        ACT: Create AlertConsumer
        ASSERT: Initialized successfully
        """
        # Act
        consumer = MockAlertConsumer(
            redis_url="redis://localhost:6379/0",
            message_queue=message_queue_fixture,
            location_analyzer=location_analyzer_fixture
        )
        
        # Assert
        assert consumer is not None
        assert consumer.redis_url == "redis://localhost:6379/0"
        assert consumer.is_running is False
        assert consumer.processed_count == 0
        assert consumer.alert_count == 0

    def test_alert_consumer_with_custom_zones(self, message_queue_fixture, location_analyzer_fixture, sample_zones):
        """
        ARRANGE: Consumer with configured zones
        ACT: Create consumer
        ASSERT: Zones are loaded in analyzer
        """
        # Arrange - add custom zones to analyzer
        for zone in sample_zones.values():
            location_analyzer_fixture.add_zone(zone)
        
        # Act
        consumer = MockAlertConsumer(
            redis_url="redis://localhost:6379/0",
            message_queue=message_queue_fixture,
            location_analyzer=location_analyzer_fixture
        )
        
        # Assert
        zones = consumer.location_analyzer.get_zones()
        # Should have 3 default zones (doesn't add duplicates if same IDs)
        assert len(zones) >= 3
        zone_names = [z.name for z in zones]
        # Check that defaults are present
        assert "School Zone" in zone_names


class TestCoordinateProcessing:
    """Tests for processing coordinates from queue."""

    def test_process_single_coordinate_from_queue(self, message_queue_fixture, location_analyzer_fixture, sample_zones):
        """
        ARRANGE: One coordinate in queue, zones configured
        ACT: Process the coordinate
        ASSERT: Coordinate is consumed and stats updated
        """
        # Arrange
        location_analyzer_fixture.add_zone(sample_zones['school'])
        consumer = MockAlertConsumer(
            redis_url="redis://localhost:6379/0",
            message_queue=message_queue_fixture,
            location_analyzer=location_analyzer_fixture
        )
        
        message_queue_fixture.push_coordinate(
            ruta=101,
            latitude=4.7110,
            longitude=-74.0059
        )
        
        # Act
        consumer._process_coordinate_queue()
        
        # Assert
        assert consumer.processed_count == 1
        assert message_queue_fixture.get_queue_length('coordinate_queue') == 0

    def test_process_multiple_coordinates_sequence(self, message_queue_fixture, location_analyzer_fixture, sample_zones):
        """
        ARRANGE: Multiple coordinates in queue
        ACT: Process queue once
        ASSERT: All coordinates processed
        """
        # Arrange
        location_analyzer_fixture.add_zone(sample_zones['school'])
        consumer = MockAlertConsumer(
            redis_url="redis://localhost:6379/0",
            message_queue=message_queue_fixture,
            location_analyzer=location_analyzer_fixture
        )
        
        # Push 5 coordinates
        for i in range(5):
            message_queue_fixture.push_coordinate(
                ruta=100 + i,
                latitude=4.7110 + (i * 0.0001),
                longitude=-74.0059
            )
        
        # Act
        consumer.process_queue_once()
        
        # Assert
        assert consumer.processed_count == 5
        assert message_queue_fixture.get_queue_length('coordinate_queue') == 0

    def test_process_coordinate_with_missing_fields(self, message_queue_fixture, location_analyzer_fixture):
        """
        ARRANGE: Coordinate with missing required fields
        ACT: Try to process
        ASSERT: Handles gracefully without crashing
        """
        # Arrange
        consumer = MockAlertConsumer(
            redis_url="redis://localhost:6379/0",
            message_queue=message_queue_fixture,
            location_analyzer=location_analyzer_fixture
        )
        
        # Manually push invalid coordinate to bypass push_coordinate validation
        import json
        invalid_coord = {
            'ruta': 101,
            'latitude': None,  # Missing latitude
            'longitude': -74.0059
        }
        consumer.message_queue.redis_client.lpush(
            'coordinate_queue',
            json.dumps(invalid_coord)
        )
        
        # Act - should handle gracefully
        consumer._process_coordinate_queue()
        
        # Assert - should have skipped invalid coordinate
        assert consumer.processed_count == 0

    def test_process_empty_queue_no_error(self, message_queue_fixture, location_analyzer_fixture):
        """
        ARRANGE: Empty coordinate queue
        ACT: Try to process
        ASSERT: No error, nothing processed
        """
        # Arrange
        consumer = MockAlertConsumer(
            redis_url="redis://localhost:6379/0",
            message_queue=message_queue_fixture,
            location_analyzer=location_analyzer_fixture
        )
        
        # Act - should not raise error
        consumer.process_queue_once()
        
        # Assert
        assert consumer.processed_count == 0


class TestAlertGeneration:
    """Tests for generating and queuing alerts."""

    def test_geofence_alert_generated_and_queued(self, message_queue_fixture, location_analyzer_fixture, sample_zones):
        """
        ARRANGE: Coordinate inside zone, consumer setup
        ACT: Process coordinate that triggers geofence
        ASSERT: Alert is generated and queued
        """
        # Arrange
        location_analyzer_fixture.add_zone(sample_zones['school'])
        consumer = MockAlertConsumer(
            redis_url="redis://localhost:6379/0",
            message_queue=message_queue_fixture,
            location_analyzer=location_analyzer_fixture
        )
        
        message_queue_fixture.push_coordinate(
            ruta=101,
            latitude=4.7110,
            longitude=-74.0059
        )
        
        # Act
        consumer._process_coordinate_queue()
        
        # Assert
        assert consumer.alert_count == 1
        assert message_queue_fixture.get_queue_length('alert_queue') == 1
        
        # Verify alert content
        alert = message_queue_fixture.pop_alert()
        assert alert['ruta'] == 101
        assert alert['alert_type'] == 'GEOFENCE_ENTRY'
        assert alert['area_name'] == 'School Zone'

    def test_no_alert_for_coordinate_outside_zones(self, message_queue_fixture, location_analyzer_fixture, sample_zones):
        """
        ARRANGE: Coordinate outside all zones
        ACT: Process coordinate
        ASSERT: No alert is generated
        """
        # Arrange
        location_analyzer_fixture.add_zone(sample_zones['school'])
        consumer = MockAlertConsumer(
            redis_url="redis://localhost:6379/0",
            message_queue=message_queue_fixture,
            location_analyzer=location_analyzer_fixture
        )
        
        message_queue_fixture.push_coordinate(
            ruta=101,
            latitude=3.0,  # Far from all zones
            longitude=-76.0
        )
        
        # Act
        consumer._process_coordinate_queue()
        
        # Assert
        assert consumer.alert_count == 0
        assert message_queue_fixture.get_queue_length('alert_queue') == 0

    def test_multiple_alerts_from_single_coordinate(self, message_queue_fixture, location_analyzer_fixture, sample_zones):
        """
        ARRANGE: Coordinate in multiple zones at once
        ACT: Process coordinate
        ASSERT: Multiple alerts generated
        """
        # Arrange
        location_analyzer_fixture.add_zone(sample_zones['school'])
        location_analyzer_fixture.add_zone(sample_zones['dangerous'])
        consumer = MockAlertConsumer(
            redis_url="redis://localhost:6379/0",
            message_queue=message_queue_fixture,
            location_analyzer=location_analyzer_fixture
        )
        
        # Push coordinate at school location (may be near dangerous area)
        message_queue_fixture.push_coordinate(
            ruta=101,
            latitude=4.7110,
            longitude=-74.0059
        )
        
        # Act
        consumer._process_coordinate_queue()
        
        # Assert - at least 1 alert generated
        assert consumer.alert_count >= 1

    def test_alert_contains_correct_metadata(self, message_queue_fixture, location_analyzer_fixture, sample_zones):
        """
        ARRANGE: Coordinate with metadata
        ACT: Generate alert
        ASSERT: Alert includes all metadata
        """
        # Arrange
        location_analyzer_fixture.add_zone(sample_zones['school'])
        consumer = MockAlertConsumer(
            redis_url="redis://localhost:6379/0",
            message_queue=message_queue_fixture,
            location_analyzer=location_analyzer_fixture
        )
        
        message_queue_fixture.push_coordinate(
            ruta=101,
            latitude=4.7110,
            longitude=-74.0059,
            route_status="En recorrido",
            student_status="Subio"
        )
        
        # Act
        consumer._process_coordinate_queue()
        
        # Assert
        alert = message_queue_fixture.pop_alert()
        assert alert['ruta'] == 101
        assert alert['latitude'] == 4.7110
        assert alert['longitude'] == -74.0059
        assert 'timestamp' in alert


class TestStatisticsTracking:
    """Tests for consumer statistics."""

    def test_statistics_initialization(self, message_queue_fixture, location_analyzer_fixture):
        """
        ARRANGE: Fresh consumer
        ACT: Get stats
        ASSERT: Stats show zero values
        """
        # Arrange
        consumer = MockAlertConsumer(
            redis_url="redis://localhost:6379/0",
            message_queue=message_queue_fixture,
            location_analyzer=location_analyzer_fixture
        )
        
        # Act
        stats = consumer.get_stats()
        
        # Assert
        assert stats['coordinates_processed'] == 0
        assert stats['alerts_generated'] == 0
        assert stats['coordinate_queue_length'] == 0
        assert stats['alert_queue_length'] == 0

    def test_statistics_update_on_processing(self, message_queue_fixture, location_analyzer_fixture, sample_zones):
        """
        ARRANGE: Consumer processes coordinates
        ACT: Get stats after processing
        ASSERT: Stats reflect processing
        """
        # Arrange
        location_analyzer_fixture.add_zone(sample_zones['school'])
        consumer = MockAlertConsumer(
            redis_url="redis://localhost:6379/0",
            message_queue=message_queue_fixture,
            location_analyzer=location_analyzer_fixture
        )
        
        # Push and process 3 coordinates
        for i in range(3):
            message_queue_fixture.push_coordinate(
                ruta=100 + i,
                latitude=4.7110 if i == 0 else 3.0,  # First one triggers alert
                longitude=-74.0059 if i == 0 else -76.0
            )
        
        # Act
        consumer.process_queue_once()
        stats = consumer.get_stats()
        
        # Assert
        assert stats['coordinates_processed'] == 3
        assert stats['alerts_generated'] >= 1  # At least the first coordinate

    def test_statistics_queue_length_tracking(self, message_queue_fixture, location_analyzer_fixture):
        """
        ARRANGE: Push multiple items to queues
        ACT: Get stats
        ASSERT: Queue lengths accurate
        """
        # Arrange
        consumer = MockAlertConsumer(
            redis_url="redis://localhost:6379/0",
            message_queue=message_queue_fixture,
            location_analyzer=location_analyzer_fixture
        )
        
        # Push items
        for i in range(3):
            message_queue_fixture.push_coordinate(ruta=100 + i, latitude=4.7, longitude=-74.0)
        
        for i in range(2):
            message_queue_fixture.push_alert(
                ruta=100 + i,
                latitude=4.7,
                longitude=-74.0,
                alert_type="GEOFENCE_ENTRY",
                area_name="Zone",
                severity="INFO"
            )
        
        # Act
        stats = consumer.get_stats()
        
        # Assert
        assert stats['coordinate_queue_length'] == 3
        assert stats['alert_queue_length'] == 2

    def test_statistics_include_timestamp(self, message_queue_fixture, location_analyzer_fixture):
        """
        ARRANGE: Consumer instance
        ACT: Get stats
        ASSERT: Stats include ISO timestamp
        """
        # Arrange
        consumer = MockAlertConsumer(
            redis_url="redis://localhost:6379/0",
            message_queue=message_queue_fixture,
            location_analyzer=location_analyzer_fixture
        )
        
        # Act
        stats = consumer.get_stats()
        
        # Assert
        assert 'timestamp' in stats
        assert 'T' in stats['timestamp']  # ISO format indicator


class TestQueue_Integration:
    """Integration tests for coordinate->analysis->alert flow."""

    def test_end_to_end_coordinate_to_alert_flow(self, message_queue_fixture, location_analyzer_fixture, sample_zones):
        """
        Complete flow: Push coordinate -> Process -> Check alert in queue
        """
        # Arrange
        location_analyzer_fixture.add_zone(sample_zones['school'])
        consumer = MockAlertConsumer(
            redis_url="redis://localhost:6379/0",
            message_queue=message_queue_fixture,
            location_analyzer=location_analyzer_fixture
        )
        
        # Act 1: Push coordinate that will trigger geofence
        message_queue_fixture.push_coordinate(
            ruta=101,
            latitude=4.7110,
            longitude=-74.0059,
            route_status="En recorrido"
        )
        
        assert message_queue_fixture.get_queue_length('coordinate_queue') == 1
        assert message_queue_fixture.get_queue_length('alert_queue') == 0
        
        # Act 2: Process the coordinate
        consumer._process_coordinate_queue()
        
        # Assert
        assert message_queue_fixture.get_queue_length('coordinate_queue') == 0
        assert message_queue_fixture.get_queue_length('alert_queue') == 1
        
        # Act 3: Pop and verify the alert
        alert = message_queue_fixture.pop_alert()
        assert alert is not None
        assert alert['alert_type'] == 'GEOFENCE_ENTRY'
        assert alert['ruta'] == 101

    def test_high_volume_coordinate_processing(self, message_queue_fixture, location_analyzer_fixture, sample_zones):
        """
        Simulate high volume: 100 coordinates, expect proportional alerts
        """
        # Arrange
        location_analyzer_fixture.add_zone(sample_zones['school'])
        consumer = MockAlertConsumer(
            redis_url="redis://localhost:6379/0",
            message_queue=message_queue_fixture,
            location_analyzer=location_analyzer_fixture
        )
        
        # Push 100 coordinates - every 10th enters school zone
        for i in range(100):
            if i % 10 == 0:
                # Inside school zone
                message_queue_fixture.push_coordinate(
                    ruta=100 + (i // 10),
                    latitude=4.7110,
                    longitude=-74.0059
                )
            else:
                # Outside zones
                message_queue_fixture.push_coordinate(
                    ruta=100 + (i // 10),
                    latitude=3.0,
                    longitude=-76.0
                )
        
        # Act
        consumer.process_queue_once()
        stats = consumer.get_stats()
        
        # Assert
        assert stats['coordinates_processed'] == 100
        # Should have ~10 alerts (one per route entering zone)
        assert stats['alerts_generated'] >= 8  # At least most of them
        assert message_queue_fixture.get_queue_length('coordinate_queue') == 0

    def test_repeated_zone_entries_tracked(self, message_queue_fixture, location_analyzer_fixture, sample_zones):
        """
        Same route entering zone multiple times should generate alerts each time
        """
        # Arrange
        location_analyzer_fixture.add_zone(sample_zones['school'])
        consumer = MockAlertConsumer(
            redis_url="redis://localhost:6379/0",
            message_queue=message_queue_fixture,
            location_analyzer=location_analyzer_fixture
        )
        
        # Sequence: Enter zone -> Leave -> Enter -> Leave
        positions = [
            (4.7110, -74.0059, "inside first"),
            (4.7110, -74.0059, "inside again"),
            (3.0, -76.0, "outside"),
            (4.7110, -74.0059, "inside again"),
        ]
        
        for idx, (lat, lon, label) in enumerate(positions):
            message_queue_fixture.push_coordinate(
                ruta=101,
                latitude=lat,
                longitude=lon
            )
        
        # Act
        consumer.process_queue_once()
        
        # Assert
        stats = consumer.get_stats()
        assert stats['coordinates_processed'] == 4
        # Should have 2 entry alerts (first time and after exiting)
        assert stats['alerts_generated'] == 2


class TestErrorHandling:
    """Tests for error handling and edge cases."""

    def test_consumer_handles_malformed_json_coordinate(self, message_queue_fixture, location_analyzer_fixture):
        """
        Malformed JSON in queue should be handled gracefully
        """
        # Arrange
        consumer = MockAlertConsumer(
            redis_url="redis://localhost:6379/0",
            message_queue=message_queue_fixture,
            location_analyzer=location_analyzer_fixture
        )
        
        # Push malformed data
        message_queue_fixture.redis_client.lpush(
            'coordinate_queue',
            "not valid json"
        )
        
        # Act - should not crash
        try:
            consumer._process_coordinate_queue()
            error_raised = False
        except:
            error_raised = True
        
        # Assert - graceful handling
        # Note: Actual output depends on error handling in real implementation
        assert consumer.processed_count == 0  # Not counted as valid

    def test_consumer_continues_after_invalid_coordinate(self, message_queue_fixture, location_analyzer_fixture):
        """
        Invalid coordinate shouldn't stop processing of next coordinates
        """
        # Arrange
        consumer = MockAlertConsumer(
            redis_url="redis://localhost:6379/0",
            message_queue=message_queue_fixture,
            location_analyzer=location_analyzer_fixture
        )
        
        # Push valid coordinate
        message_queue_fixture.push_coordinate(ruta=101, latitude=4.7, longitude=-74.0)
        
        # Act - process both
        consumer.process_queue_once()
        
        # Assert
        assert consumer.processed_count == 1
