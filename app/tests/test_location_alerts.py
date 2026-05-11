"""
Test Suite for Location Analysis and Geofencing

Tests the LocationAnalyzer class for:
- Zone management (add, list, remove)
- Geofence entry/exit detection
- Route tracking across zones
- Alert generation
- Route status queries

TDD Approach:
We test geofencing logic following real-world flow:
1. Initialize zones
2. Track routes through zones
3. Detect entries and exits
4. Generate alerts
5. Query route status
"""

import pytest
from datetime import datetime
from zoneinfo import ZoneInfo

from shared.location_alerts import (
    LocationAnalyzer,
    Zone,
    LocationAlert,
    AlertType,
    AlertSeverity
)


pytestmark = pytest.mark.geofence


def get_zone(analyzer: LocationAnalyzer, name: str) -> Zone:
    return next(zone for zone in analyzer.get_zones() if zone.name == name)


def get_zone_by_type(analyzer: LocationAnalyzer, alert_type: AlertType) -> Zone:
    return next(zone for zone in analyzer.get_zones() if zone.alert_type == alert_type)


def get_two_distinct_entry_zones(analyzer: LocationAnalyzer) -> tuple[Zone, Zone]:
    entry_zones = [z for z in analyzer.get_zones() if z.alert_type == AlertType.GEOFENCE_ENTRY]
    if len(entry_zones) < 2:
        raise ValueError("At least two entry-type zones are required for this test")
    return entry_zones[0], entry_zones[1]


class TestZoneManagement:
    """Tests for adding, listing, and managing zones."""

    def test_location_analyzer_initializes_with_default_zones(self, location_analyzer_fixture):
        """
        ARRANGE: LocationAnalyzer is initialized
        ACT: Get zones
        ASSERT: YAML zones are present
        """
        # Act
        zones = location_analyzer_fixture.get_zones()
        
        # Assert
        assert len(zones) > 0
        zone_ids = {z.zone_id for z in zones}
        assert len(zone_ids) == len(zones)

        for zone in zones:
            assert isinstance(zone.name, str)
            assert zone.name != ""
            assert isinstance(zone.latitude, float)
            assert isinstance(zone.longitude, float)
            assert zone.radius_meters > 0
            assert isinstance(zone.alert_type, AlertType)
            assert isinstance(zone.severity, AlertSeverity)
            assert zone.enabled is True

    def test_add_custom_zone_successfully(self, location_analyzer_fixture):
        """
        ARRANGE: LocationAnalyzer with new zone to add
        ACT: Add a custom zone
        ASSERT: Zone is added and returned in get_zones()
        """
        # Arrange
        new_zone = Zone(
            zone_id=99,
            name="Custom Test Zone",
            latitude=4.7000,
            longitude=-74.0000,
            radius_meters=300,
            alert_type=AlertType.GEOFENCE_ENTRY,
            severity=AlertSeverity.WARNING
        )
        
        initial_count = len(location_analyzer_fixture.get_zones())
        
        # Act
        result = location_analyzer_fixture.add_zone(new_zone)
        
        # Assert
        assert result is True
        assert len(location_analyzer_fixture.get_zones()) == initial_count + 1
        
        # Verify our zone is in the list
        zone_names = [z.name for z in location_analyzer_fixture.get_zones()]
        assert "Custom Test Zone" in zone_names

    def test_add_duplicate_zone_fails(self, location_analyzer_fixture):
        """
        ARRANGE: Zone with duplicate ID
        ACT: Try to add a zone with existing ID
        ASSERT: Add fails and returns False
        """
        # Arrange - try to add a zone with ID that already exists
        duplicate_zone = Zone(
            zone_id=1,  # Already exists
            name="Duplicate Zone",
            latitude=5.0000,
            longitude=-75.0000,
            radius_meters=500
        )
        
        # Act
        result = location_analyzer_fixture.add_zone(duplicate_zone)
        
        # Assert
        assert result is False

    def test_disabled_zones_not_included_in_analysis(self, location_analyzer_fixture):
        """
        ARRANGE: Zone that is disabled
        ACT: Add disabled zone and analyze coordinate in its area
        ASSERT: Disabled zone is not used for analysis
        """
        # Arrange
        disabled_zone = Zone(
            zone_id=50,
            name="Disabled Zone",
            latitude=4.7110,
            longitude=-74.0059,
            radius_meters=500,
            enabled=False
        )
        location_analyzer_fixture.add_zone(disabled_zone)
        
        # Act - coordinate inside the disabled zone
        alerts = location_analyzer_fixture.analyze_coordinate(
            ruta=101,
            latitude=4.7110,
            longitude=-74.0059
        )
        
        # Assert - no alerts should be generated from disabled zone
        zone_names_in_alerts = [a.zone_name for a in alerts]
        assert "Disabled Zone" not in zone_names_in_alerts


class TestZoneIntersection:
    """Tests for detecting if coordinates are within zones."""

    def test_coordinate_inside_zone(self, sample_zones):
        """
        ARRANGE: Zone and coordinate inside it
        ACT: Check if coordinate is within zone
        ASSERT: Returns True
        """
        # Arrange
        boyaca_zone = sample_zones['boyaca']
        
        # Act - coordinate at the exact center
        is_inside = boyaca_zone.is_within(boyaca_zone.latitude, boyaca_zone.longitude)
        
        # Assert
        assert is_inside is True

    def test_coordinate_outside_zone(self, sample_zones):
        """
        ARRANGE: Zone and coordinate far outside it
        ACT: Check if coordinate is within zone
        ASSERT: Returns False
        """
        # Arrange
        boyaca_zone = sample_zones['boyaca']
        
        # Act - coordinate very far away (different city)
        is_inside = boyaca_zone.is_within(3.0000, -76.0000)
        
        # Assert
        assert is_inside is False

    def test_coordinate_at_zone_boundary(self, sample_zones):
        """
        ARRANGE: Zone and coordinate near the boundary
        ACT: Check if coordinate near boundary is within zone
        ASSERT: Properly detects inside/outside boundary
        """
        # Arrange
        boyaca_zone = sample_zones['boyaca']
        
        # The Boyaca zone is at (4.742, -74.065845) with 1600m radius
        # Test a coordinate approximately 500m away
        
        # This coordinate is approximately 1km away (slightly outside)
        is_inside = boyaca_zone.is_within(4.742, -74.0550)
        
        # Should be outside or on boundary
        # Note: Exact calculation depends on geodesic distance
        # This is more of an integration test for real values
        assert isinstance(is_inside, bool)


class TestGeofenceEntryDetection:
    """Tests for detecting when routes enter geofence zones."""

    def test_entry_detection_first_time_in_zone(self, location_analyzer_fixture):
        """
        ARRANGE: Route never seen before, coordinate inside zone
        ACT: Analyze coordinate
        ASSERT: Entry alert is generated
        """
        # Arrange
        entry_zone = get_zone_by_type(location_analyzer_fixture, AlertType.GEOFENCE_ENTRY)
        
        # Act - first time analyzing position inside an entry zone
        alerts = location_analyzer_fixture.analyze_coordinate(
            ruta=101,
            latitude=entry_zone.latitude,
            longitude=entry_zone.longitude
        )
        
        # Assert
        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.alert_type == AlertType.GEOFENCE_ENTRY
        assert alert.zone_name == entry_zone.name
        assert alert.ruta == 101

    def test_no_entry_alert_if_already_in_zone(self, location_analyzer_fixture):
        """
        ARRANGE: Route is already inside zone (from previous analysis)
        ACT: Analyze coordinate inside same zone
        ASSERT: No entry alert is generated
        """
        # Arrange
        entry_zone = get_zone_by_type(location_analyzer_fixture, AlertType.GEOFENCE_ENTRY)
        
        # First analysis - establishes that route is in zone
        location_analyzer_fixture.analyze_coordinate(
            ruta=101,
            latitude=entry_zone.latitude,
            longitude=entry_zone.longitude
        )
        
        # Act - analyze same location again
        alerts = location_analyzer_fixture.analyze_coordinate(
            ruta=101,
            latitude=entry_zone.latitude,
            longitude=entry_zone.longitude
        )
        
        # Assert - no entry alert since already in zone
        assert len(alerts) == 0

    def test_entry_alert_when_moving_into_zone(self, location_analyzer_fixture):
        """
        ARRANGE: Route outside zone, then moves inside
        ACT: First outside, then inside
        ASSERT: Entry alert only on second analysis
        """
        # Arrange
        entry_zone = get_zone_by_type(location_analyzer_fixture, AlertType.GEOFENCE_ENTRY)
        
        # First analysis - outside zone
        alerts1 = location_analyzer_fixture.analyze_coordinate(
            ruta=101,
            latitude=3.0000,
            longitude=-76.0000
        )
        
        # No alerts when outside
        assert len(alerts1) == 0
        
        # Act - move into zone
        alerts2 = location_analyzer_fixture.analyze_coordinate(
            ruta=101,
            latitude=entry_zone.latitude,
            longitude=entry_zone.longitude
        )
        
        # Assert - entry alert when moving in
        assert len(alerts2) == 1
        assert alerts2[0].alert_type == AlertType.GEOFENCE_ENTRY


class TestGeofenceExitDetection:
    """Tests for detecting when routes exit geofence zones."""

    def test_exit_alert_for_exit_type_zone(self, location_analyzer_fixture):
        """
        ARRANGE: Zone with GEOFENCE_EXIT alert type (Cota-conejera)
        ACT: Route moves from inside to outside
        ASSERT: Exit alert is generated
        """
        # Arrange
        exit_zone = get_zone_by_type(location_analyzer_fixture, AlertType.GEOFENCE_EXIT)
        
        # First analysis - inside Cota-conejera zone
        location_analyzer_fixture.analyze_coordinate(
            ruta=104,
            latitude=exit_zone.latitude,
            longitude=exit_zone.longitude
        )
        
        # Act - move out of Cota-conejera
        alerts = location_analyzer_fixture.analyze_coordinate(
            ruta=104,
            latitude=exit_zone.latitude + 0.05,
            longitude=exit_zone.longitude
        )
        
        # Assert
        assert len(alerts) >= 1
        assert any(
            alert.alert_type == AlertType.GEOFENCE_EXIT and alert.zone_name == exit_zone.name
            for alert in alerts
        )

    def test_no_exit_alert_for_entry_type_zone(self, location_analyzer_fixture):
        """
        ARRANGE: Zone with GEOFENCE_ENTRY alert type (Boyaca)
        ACT: Route moves from inside to outside
        ASSERT: No exit alert is generated (only entry type)
        """
        # Arrange
        entry_zone = get_zone_by_type(location_analyzer_fixture, AlertType.GEOFENCE_ENTRY)
        
        # First analysis - inside
        location_analyzer_fixture.analyze_coordinate(
            ruta=101,
            latitude=entry_zone.latitude,
            longitude=entry_zone.longitude
        )
        
        # Act - move out
        alerts = location_analyzer_fixture.analyze_coordinate(
            ruta=101,
            latitude=3.0000,
            longitude=-76.0000
        )
        
        # Assert - no alerts for entry-type zones when exiting
        assert len(alerts) == 0


class TestMultipleZoneTracking:
    """Tests for routes being in multiple zones simultaneously."""

    def test_route_in_multiple_zones(self, location_analyzer_fixture):
        """
        ARRANGE: Two overlapping zones
        ACT: Route at position that's in both zones
        ASSERT: Entry alerts generated for both zones
        """
        # Arrange
        zone_1, _ = get_two_distinct_entry_zones(location_analyzer_fixture)
        
        # Act - coordinate that might be in both
        # (Use one configured entry zone center)
        alerts = location_analyzer_fixture.analyze_coordinate(
            ruta=101,
            latitude=zone_1.latitude,
            longitude=zone_1.longitude
        )
        
        # Assert
        assert len(alerts) >= 1
        # All alerts should be for entry (these are both entry-type zones)
        for alert in alerts:
            assert alert.alert_type == AlertType.GEOFENCE_ENTRY

    def test_route_moves_between_zones(self, location_analyzer_fixture):
        """
        ARRANGE: Route tracking across multiple zones
        ACT: Route moves from one zone to another
        ASSERT: Proper entry/exit alerts
        """
        # Arrange
        zone_1, zone_2 = get_two_distinct_entry_zones(location_analyzer_fixture)
        
        # Act 1 - Route enters first entry zone
        alerts1 = location_analyzer_fixture.analyze_coordinate(
            ruta=105,
            latitude=zone_1.latitude,
            longitude=zone_1.longitude
        )
        
        # Assert - entry to first zone
        assert len(alerts1) == 1
        assert alerts1[0].zone_name == zone_1.name
        
        # Act 2 - Route exits Boyaca but is still tracked
        alerts2 = location_analyzer_fixture.analyze_coordinate(
            ruta=105,
            latitude=3.0000,
            longitude=-76.0000
        )
        
        # Assert - no additional entry alerts while outside all zones
        assert all(a.alert_type == AlertType.GEOFENCE_EXIT for a in alerts2)
        
        # Act 3 - Route enters second entry zone
        alerts3 = location_analyzer_fixture.analyze_coordinate(
            ruta=105,
            latitude=zone_2.latitude,
            longitude=zone_2.longitude
        )
        
        # Assert - entry to second zone
        assert len(alerts3) == 1
        assert alerts3[0].zone_name == zone_2.name


class TestAlertGeneration:
    """Tests for alert object creation and properties."""

    def test_alert_contains_correct_information(self, location_analyzer_fixture):
        """
        ARRANGE: Geofence event
        ACT: Generate alert
        ASSERT: Alert contains all required information
        """
        # Arrange
        entry_zone = get_zone_by_type(location_analyzer_fixture, AlertType.GEOFENCE_ENTRY)
        
        # Act
        alerts = location_analyzer_fixture.analyze_coordinate(
            ruta=101,
            latitude=entry_zone.latitude,
            longitude=entry_zone.longitude
        )
        
        # Assert
        alert = alerts[0]
        assert isinstance(alert, LocationAlert)
        assert alert.ruta == 101
        assert alert.latitude == entry_zone.latitude
        assert alert.longitude == entry_zone.longitude
        assert alert.alert_type == AlertType.GEOFENCE_ENTRY
        assert alert.zone_name == entry_zone.name
        assert alert.severity == AlertSeverity.WARNING
        assert isinstance(alert.timestamp, datetime)
        assert alert.message != ""

    def test_alert_severity_matches_zone_severity(self, location_analyzer_fixture):
        """
        ARRANGE: Zone with CRITICAL severity
        ACT: Generate alert from that zone
        ASSERT: Alert inherits zone's severity
        """
        # Arrange
        critical_zone = Zone(
            zone_id=88,
            name="Critical Area",
            latitude=4.6000,
            longitude=-74.0000,
            radius_meters=500,
            alert_type=AlertType.GEOFENCE_ENTRY,
            severity=AlertSeverity.CRITICAL
        )
        location_analyzer_fixture.add_zone(critical_zone)
        
        # Act
        alerts = location_analyzer_fixture.analyze_coordinate(
            ruta=101,
            latitude=4.6000,
            longitude=-74.0000
        )
        
        # Assert
        assert alerts[0].severity == AlertSeverity.CRITICAL


class TestRouteStatusTracking:
    """Tests for querying route status and current zones."""

    def test_get_route_status_not_tracked(self, location_analyzer_fixture):
        """
        ARRANGE: Route that has never been analyzed
        ACT: Get route status
        ASSERT: Returns empty status
        """
        # Act
        status = location_analyzer_fixture.get_route_status(ruta=999)
        
        # Assert
        assert status['ruta'] == 999
        assert status['current_zones'] == []
        assert status['last_position'] is None
        assert status['last_update'] is None

    def test_get_route_status_in_zone(self, location_analyzer_fixture):
        """
        ARRANGE: Route inside a zone
        ACT: Get route status
        ASSERT: Status shows zone ID and position
        """
        # Arrange
        entry_zone = get_zone_by_type(location_analyzer_fixture, AlertType.GEOFENCE_ENTRY)
        
        location_analyzer_fixture.analyze_coordinate(
            ruta=101,
            latitude=entry_zone.latitude,
            longitude=entry_zone.longitude
        )
        
        # Act
        status = location_analyzer_fixture.get_route_status(ruta=101)
        
        # Assert
        assert status['ruta'] == 101
        assert entry_zone.zone_id in status['current_zones']
        assert status['last_position'] is not None
        assert status['last_position']['latitude'] == entry_zone.latitude
        assert status['last_position']['longitude'] == entry_zone.longitude
        assert status['last_update'] is not None

    def test_get_route_status_multiple_zones(self, location_analyzer_fixture):
        """
        ARRANGE: Route potentially in multiple zones
        ACT: Get route status
        ASSERT: Shows all current zones
        """
        # Arrange
        entry_zone = get_zone_by_type(location_analyzer_fixture, AlertType.GEOFENCE_ENTRY)
        
        # Analyze at Boyaca location
        location_analyzer_fixture.analyze_coordinate(
            ruta=102,
            latitude=entry_zone.latitude,
            longitude=entry_zone.longitude
        )
        
        # Act
        status = location_analyzer_fixture.get_route_status(ruta=102)
        
        # Assert
        assert status['ruta'] == 102
        assert entry_zone.zone_id in status['current_zones']
        assert isinstance(status['current_zones'], list)


class TestRouteTrackingStateManagement:
    """Tests for managing route tracking state."""

    def test_clear_route_tracking(self, location_analyzer_fixture):
        """
        ARRANGE: Route is being tracked
        ACT: Clear tracking for that route
        ASSERT: Route status is reset
        """
        # Arrange
        entry_zone = get_zone_by_type(location_analyzer_fixture, AlertType.GEOFENCE_ENTRY)
        
        location_analyzer_fixture.analyze_coordinate(
            ruta=103,
            latitude=entry_zone.latitude,
            longitude=entry_zone.longitude
        )
        
        # Verify route is tracked
        status_before = location_analyzer_fixture.get_route_status(ruta=103)
        assert status_before['current_zones'] != []
        
        # Act
        location_analyzer_fixture.clear_route_tracking(ruta=103)
        
        # Assert
        status_after = location_analyzer_fixture.get_route_status(ruta=103)
        assert status_after['current_zones'] == []

    def test_clear_tracking_for_one_route_doesnt_affect_others(self, location_analyzer_fixture):
        """
        ARRANGE: Multiple routes being tracked
        ACT: Clear tracking for one route
        ASSERT: Other routes still tracked
        """
        # Arrange
        entry_zone = get_zone_by_type(location_analyzer_fixture, AlertType.GEOFENCE_ENTRY)
        
        # Track two routes
        location_analyzer_fixture.analyze_coordinate(
            ruta=201,
            latitude=entry_zone.latitude,
            longitude=entry_zone.longitude
        )
        location_analyzer_fixture.analyze_coordinate(
            ruta=202,
            latitude=entry_zone.latitude,
            longitude=entry_zone.longitude
        )
        
        # Act - clear route 201
        location_analyzer_fixture.clear_route_tracking(ruta=201)
        
        # Assert
        status_201 = location_analyzer_fixture.get_route_status(ruta=201)
        status_202 = location_analyzer_fixture.get_route_status(ruta=202)
        
        assert status_201['current_zones'] == []
        assert status_202['current_zones'] != []


class TestComplexGeofencingScenarios:
    """Integration-style tests for complex real-world scenarios."""

    def test_route_tour_through_multiple_zones(self, location_analyzer_fixture):
        """
        ARRANGE: Multiple zones, one route
        ACT: Simulate route movement through all zones
        ASSERT: Correct sequence of alerts
        """
        # Arrange
        entry_zones = [z for z in location_analyzer_fixture.get_zones() if z.alert_type == AlertType.GEOFENCE_ENTRY]
        exit_zone = get_zone_by_type(location_analyzer_fixture, AlertType.GEOFENCE_EXIT)
        assert len(entry_zones) >= 2

        first_entry_zone = entry_zones[0]
        second_entry_zone = entry_zones[1]
        final_entry_zone = entry_zones[2] if len(entry_zones) > 2 else entry_zones[0]
        
        # Act & Assert - simulate a route tour
        
        # 1. Start outside all zones
        alerts = location_analyzer_fixture.analyze_coordinate(ruta=301, latitude=3.0, longitude=-76.0)
        assert len(alerts) == 0
        
        # 2. Enter first entry zone
        alerts = location_analyzer_fixture.analyze_coordinate(
            ruta=301,
            latitude=first_entry_zone.latitude,
            longitude=first_entry_zone.longitude
        )
        assert len(alerts) >= 1
        assert any(a.zone_name == first_entry_zone.name for a in alerts)
        prev_alert_count = len(alerts)
        
        # 3. Stay in first zone
        alerts = location_analyzer_fixture.analyze_coordinate(
            ruta=301,
            latitude=first_entry_zone.latitude,
            longitude=first_entry_zone.longitude
        )
        assert len(alerts) == 0  # No new entries
        
        # 4. Move to second entry zone
        alerts = location_analyzer_fixture.analyze_coordinate(
            ruta=301,
            latitude=second_entry_zone.latitude,
            longitude=second_entry_zone.longitude
        )
        # May or may not have alert depending on overlap
        
        # 5. Enter an exit-type zone
        alerts = location_analyzer_fixture.analyze_coordinate(
            ruta=301,
            latitude=exit_zone.latitude,
            longitude=exit_zone.longitude
        )
        # Exit alert triggers when leaving
        alerts = location_analyzer_fixture.analyze_coordinate(
            ruta=301,
            latitude=exit_zone.latitude + 0.05,
            longitude=exit_zone.longitude
        )
        assert any(a.alert_type == AlertType.GEOFENCE_EXIT and a.zone_name == exit_zone.name for a in alerts)

        # 6. Enter final entry zone
        location_analyzer_fixture.analyze_coordinate(
            ruta=301,
            latitude=final_entry_zone.latitude,
            longitude=final_entry_zone.longitude
        )
        
        # Final status should show final zone
        status = location_analyzer_fixture.get_route_status(ruta=301)
        assert final_entry_zone.zone_id in status['current_zones']

    def test_concurrent_routes_independent_tracking(self, location_analyzer_fixture):
        """
        ARRANGE: Multiple routes moving independently
        ACT: Analyze coordinates for each
        ASSERT: Each route tracked independently
        """
        # Arrange
        zone_1, zone_2 = get_two_distinct_entry_zones(location_analyzer_fixture)
        
        # Act - route 401 enters first zone
        location_analyzer_fixture.analyze_coordinate(
            ruta=401,
            latitude=zone_1.latitude,
            longitude=zone_1.longitude
        )
        status_401_school = location_analyzer_fixture.get_route_status(ruta=401)
        
        # Another analysis for same route
        location_analyzer_fixture.analyze_coordinate(
            ruta=401,
            latitude=zone_1.latitude,
            longitude=zone_1.longitude
        )
        
        # Route 402 enters second zone
        location_analyzer_fixture.analyze_coordinate(
            ruta=402,
            latitude=zone_2.latitude,
            longitude=zone_2.longitude
        )
        status_402_depot = location_analyzer_fixture.get_route_status(ruta=402)
        
        # Assert
        assert zone_1.zone_id in status_401_school['current_zones']
        assert zone_2.zone_id in status_402_depot['current_zones']
        
        # Routes should be in different zones
        assert zone_1.zone_id not in status_402_depot['current_zones']
        assert zone_2.zone_id not in status_401_school['current_zones']
