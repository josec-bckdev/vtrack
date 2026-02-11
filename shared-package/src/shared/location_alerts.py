"""
Location analysis and geofencing for coordinate-based alerts.
Analyzes coordinate data and generates alerts based on predefined areas/zones.
"""

import logging
from typing import Optional, List
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import yaml

from geopy.distance import geodesic

logger = logging.getLogger(__name__)

class AlertType(str, Enum):
    """Types of location-based alerts."""
    GEOFENCE_ENTRY = "GEOFENCE_ENTRY"
    GEOFENCE_EXIT = "GEOFENCE_EXIT"
    UNUSUAL_LOCATION = "UNUSUAL_LOCATION"
    HALT_ALERT = "HALT_ALERT"
    SLOW_SPEED = "SLOW_SPEED"

class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"

@dataclass
class Zone:
    """Represents a geographical zone/area for geofencing."""
    zone_id: int
    name: str
    latitude: float
    longitude: float
    radius_meters: float  # Radius of the zone in meters
    alert_type: AlertType = AlertType.GEOFENCE_ENTRY
    severity: AlertSeverity = AlertSeverity.WARNING
    enabled: bool = True
    
    def is_within(self, lat: float, lon: float) -> bool:
        """
        Check if a coordinate is within this zone.
        
        Args:
            lat: Latitude coordinate
            lon: Longitude coordinate
            
        Returns:
            True if coordinate is within zone, False otherwise
        """
        try:
            zone_point = (self.latitude, self.longitude)
            coord_point = (lat, lon)
            distance = geodesic(zone_point, coord_point).meters
            return distance <= self.radius_meters
        except Exception as e:
            logger.error(f"Error calculating distance for zone {self.name}: {e}")
            return False

@dataclass
class LocationAlert:
    """Represents a location-based alert."""
    ruta: int
    latitude: float
    longitude: float
    alert_type: AlertType
    zone_name: str
    severity: AlertSeverity
    timestamp: datetime
    message: str = ""

class LocationAnalyzer:
    """Analyzes coordinate data and generates location-based alerts."""
    
    def __init__(self):
        """Initialize the location analyzer with default zones."""
        self.zones: List[Zone] = []
        self.tracking_state = {}  # Track if routes are within zones
        self._initialize_default_zones()
    
    def _initialize_default_zones(self):
        """
        Initialize zones from YAML configuration file.
        """
        zones_file = os.path.join(
            os.path.dirname(__file__),
            'zones.yaml'
        )
        
        if os.path.exists(zones_file):
            try:
                with open(zones_file, 'r') as f:
                    config = yaml.safe_load(f)
                    
                if config and 'zones' in config:
                    for zone_data in config['zones']:
                        zone = Zone(
                            zone_id=zone_data['zone_id'],
                            name=zone_data['name'],
                            latitude=zone_data['latitude'],
                            longitude=zone_data['longitude'],
                            radius_meters=zone_data['radius_meters'],
                            alert_type=AlertType(zone_data.get('alert_type', 'GEOFENCE_ENTRY')),
                            severity=AlertSeverity(zone_data.get('severity', 'WARNING')),
                            enabled=zone_data.get('enabled', True)
                        )
                        self.zones.append(zone)
                    logger.info(f"Loaded {len(self.zones)} zones from configuration")
                else:
                    logger.warning("No zones found in configuration file")
            except Exception as e:
                logger.error(f"Error loading zones from YAML file: {e}")
        else:
            logger.warning(f"Zones configuration file not found at {zones_file}")
    
    def add_zone(self, zone: Zone) -> bool:
        """
        Add a monitoring zone.
        
        Args:
            zone: Zone object to add
            
        Returns:
            True if added successfully
        """
        try:
            if not any(z.zone_id == zone.zone_id for z in self.zones):
                self.zones.append(zone)
                logger.info(f"Zone '{zone.name}' added for monitoring")
                return True
            else:
                logger.warning(f"Zone with ID {zone.zone_id} already exists")
                return False
        except Exception as e:
            logger.error(f"Error adding zone: {e}")
            return False
    
    def get_zones(self) -> List[Zone]:
        """Get all active zones."""
        return [z for z in self.zones if z.enabled]
    
    def analyze_coordinate(self, ruta: int, latitude: float, 
                          longitude: float) -> List[LocationAlert]:
        """
        Analyze a coordinate and generate alerts if needed.
        
        Args:
            ruta: Route ID
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            
        Returns:
            List of LocationAlert objects if any conditions are met
        """
        alerts = []
        
        try:
            route_key = f"ruta_{ruta}"
            current_zones = []
            
            # Check all zones
            for zone in self.get_zones():
                if zone.is_within(latitude, longitude):
                    current_zones.append(zone.zone_id)
                    
                    # Check if this is a new entry
                    previous_zones = self.tracking_state.get(route_key, {}).get('zones', [])
                    
                    if zone.zone_id not in previous_zones:
                        # New zone entry
                        alert = LocationAlert(
                            ruta=ruta,
                            latitude=latitude,
                            longitude=longitude,
                            alert_type=zone.alert_type,
                            zone_name=zone.name,
                            severity=zone.severity,
                            timestamp=datetime.now(ZoneInfo("America/Bogota")),
                            message=f"Route {ruta} entered {zone.name}"
                        )
                        alerts.append(alert)
                        logger.warning(
                            f"Alert: Route {ruta} entered zone '{zone.name}' "
                            f"at ({latitude}, {longitude})"
                        )
            
            # Check for exits from zones
            previous_zones = self.tracking_state.get(route_key, {}).get('zones', [])
            for zone_id in previous_zones:
                if zone_id not in current_zones:
                    zone = next((z for z in self.zones if z.zone_id == zone_id), None)
                    if zone and zone.alert_type == AlertType.GEOFENCE_EXIT:
                        alert = LocationAlert(
                            ruta=ruta,
                            latitude=latitude,
                            longitude=longitude,
                            alert_type=AlertType.GEOFENCE_EXIT,
                            zone_name=zone.name,
                            severity=zone.severity,
                            timestamp=datetime.now(ZoneInfo("America/Bogota")),
                            message=f"Route {ruta} exited {zone.name}"
                        )
                        alerts.append(alert)
                        logger.info(
                            f"Alert: Route {ruta} exited zone '{zone.name}' "
                            f"at ({latitude}, {longitude})"
                        )
            
            # Update tracking state
            self.tracking_state[route_key] = {
                'zones': current_zones,
                'last_lat': latitude,
                'last_lon': longitude,
                'last_update': datetime.now(ZoneInfo("America/Bogota"))
            }
            
        except Exception as e:
            logger.error(f"Error analyzing coordinate for ruta {ruta}: {e}")
        
        return alerts
    
    def get_route_status(self, ruta: int) -> dict:
        """
        Get the current tracking status of a route.
        
        Args:
            ruta: Route ID
            
        Returns:
            Dictionary with route tracking information
        """
        route_key = f"ruta_{ruta}"
        status = self.tracking_state.get(route_key, {})
        
        if status:
            return {
                'ruta': ruta,
                'current_zones': status.get('zones', []),
                'last_position': {
                    'latitude': status.get('last_lat'),
                    'longitude': status.get('last_lon'),
                },
                'last_update': status.get('last_update').isoformat() if status.get('last_update') else None
            }
        else:
            return {
                'ruta': ruta,
                'current_zones': [],
                'last_position': None,
                'last_update': None
            }
    
    def clear_route_tracking(self, ruta: int):
        """
        Clear tracking state for a route (useful for end of day).
        
        Args:
            ruta: Route ID to clear
        """
        route_key = f"ruta_{ruta}"
        if route_key in self.tracking_state:
            del self.tracking_state[route_key]
            logger.info(f"Cleared tracking state for route {ruta}")
