"""
Redis-based message queue for coordinate data and alerts.
Handles pushing coordinate data to queues for processing.
"""

import json
import logging
from typing import Optional
from datetime import datetime
from zoneinfo import ZoneInfo

import redis
from rq import Queue

logger = logging.getLogger(__name__)

class MessageQueue:
    """Manages Redis message queue for coordinate data and alerts."""
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        """
        Initialize Redis connection and queue.
        
        Args:
            redis_url: Redis connection URL
        """
        self.redis_url = redis_url
        try:
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            # Test connection
            self.redis_client.ping()
            logger.info("Redis connection established successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
        
        # Create queues for different purposes
        self.coordinate_queue = Queue('coordinates', connection=self.redis_client)
        self.alert_queue = Queue('alerts', connection=self.redis_client)
    
    def push_coordinate(self, ruta: int, latitude: float, longitude: float, 
                       position_ts: Optional[datetime] = None,
                       route_status: Optional[str] = None,
                       student_status: Optional[str] = None) -> bool:
        """
        Push coordinate data to the queue for analysis.
        
        Args:
            ruta: Route ID
            latitude: NS latitude coordinate
            longitude: EW longitude coordinate
            position_ts: Position timestamp
            route_status: Route status
            student_status: Student status
            
        Returns:
            True if successfully queued, False otherwise
        """
        try:
            coordinate_data = {
                "ruta": ruta,
                "latitude": latitude,
                "longitude": longitude,
                "position_ts": position_ts.isoformat() if position_ts else None,
                "route_status": route_status,
                "student_status": student_status,
                "queued_at": datetime.now(ZoneInfo("America/Bogota")).isoformat()
            }
            
            # Push to Redis queue
            self.redis_client.lpush(
                'coordinate_queue',
                json.dumps(coordinate_data)
            )
            logger.debug(f"Pushed coordinate to queue: Ruta {ruta} at ({latitude}, {longitude})")
            return True
            
        except Exception as e:
            logger.error(f"Error pushing coordinate to queue: {e}")
            return False
    
    def push_alert(self, ruta: int, latitude: float, longitude: float,
                  alert_type: str, area_name: str, severity: str = "INFO") -> bool:
        """
        Push an alert to the alert queue.
        
        Args:
            ruta: Route ID
            latitude: Location latitude
            longitude: Location longitude
            alert_type: Type of alert (e.g., "GEOFENCE", "SLOW_SPEED", "HALT")
            area_name: Name of the area where alert was triggered
            severity: Alert severity level (INFO, WARNING, CRITICAL)
            
        Returns:
            True if successfully queued, False otherwise
        """
        try:
            alert_data = {
                "ruta": ruta,
                "latitude": latitude,
                "longitude": longitude,
                "alert_type": alert_type,
                "area_name": area_name,
                "severity": severity,
                "timestamp": datetime.now(ZoneInfo("America/Bogota")).isoformat()
            }
            
            self.redis_client.lpush(
                'alert_queue',
                json.dumps(alert_data)
            )
            logger.info(f"Alert queued: {alert_type} for Ruta {ruta} in {area_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error pushing alert to queue: {e}")
            return False
    
    def get_queue_length(self, queue_name: str) -> int:
        """
        Get the current length of a queue.
        
        Args:
            queue_name: Name of the queue ('coordinate_queue' or 'alert_queue')
            
        Returns:
            Number of items in the queue
        """
        try:
            return self.redis_client.llen(queue_name)
        except Exception as e:
            logger.error(f"Error getting queue length: {e}")
            return 0
    
    def pop_coordinate(self) -> Optional[dict]:
        """
        Pop a coordinate from the queue.
        
        Returns:
            Coordinate data dict or None if queue is empty
        """
        try:
            data = self.redis_client.rpop('coordinate_queue')
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Error popping coordinate from queue: {e}")
            return None
    
    def pop_alert(self) -> Optional[dict]:
        """
        Pop an alert from the queue.
        
        Returns:
            Alert data dict or None if queue is empty
        """
        try:
            data = self.redis_client.rpop('alert_queue')
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Error popping alert from queue: {e}")
            return None
    
    def health_check(self) -> bool:
        """
        Check if Redis connection is healthy.
        
        Returns:
            True if connected and responding, False otherwise
        """
        try:
            return self.redis_client.ping()
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False
