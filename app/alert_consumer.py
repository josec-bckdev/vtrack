"""
Alert Consumer Service - Microservice for processing coordinate queue and generating alerts.

This service runs independently and:
1. Consumes coordinate data from Redis queue
2. Analyzes locations using geofencing
3. Generates and queues alerts
4. Can be run as a separate Docker container
"""

import json
import logging
import time
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.message_queue import MessageQueue
from app.location_alerts import LocationAnalyzer, LocationAlert

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AlertConsumer:
    """Consumer service that processes coordinates and generates location-based alerts."""
    
    def __init__(self, redis_url: str = None):
        """
        Initialize the alert consumer service.
        
        Args:
            redis_url: Redis connection URL (defaults to environment variable or localhost)
        """
        self.redis_url = redis_url or os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        self.message_queue = MessageQueue(self.redis_url)
        self.location_analyzer = LocationAnalyzer()
        self.is_running = False
        self.processed_count = 0
        self.alert_count = 0
        
        logger.info(f"Alert Consumer initialized with Redis URL: {self.redis_url}")
    
    def start(self, poll_interval: int = 1):
        """
        Start the consumer service.
        
        Args:
            poll_interval: Seconds to wait between queue checks
        """
        logger.info("Starting Alert Consumer Service...")
        self.is_running = True
        
        try:
            # Verify Redis connection
            if not self.message_queue.health_check():
                logger.error("Redis connection failed. Exiting.")
                return
            
            logger.info("Redis connection verified. Beginning to process queue...")
            
            while self.is_running:
                self._process_coordinate_queue()
                time.sleep(poll_interval)
                
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        except Exception as e:
            logger.error(f"Unexpected error in consumer loop: {e}")
        finally:
            self.stop()
    
    def _process_coordinate_queue(self):
        """Process all available coordinates in the queue."""
        coordinate = self.message_queue.pop_coordinate()
        
        if coordinate:
            try:
                # Extract coordinate data
                ruta = coordinate.get('ruta')
                latitude = coordinate.get('latitude')
                longitude = coordinate.get('longitude')
                
                if not all([ruta, latitude, longitude]):
                    logger.warning(f"Invalid coordinate data: {coordinate}")
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
                    self._queue_alert(alert)
                    self.alert_count += 1
                
                # Log statistics periodically
                if self.processed_count % 100 == 0:
                    logger.info(
                        f"Processed {self.processed_count} coordinates, "
                        f"Generated {self.alert_count} alerts"
                    )
                    
            except Exception as e:
                logger.error(f"Error processing coordinate: {e}")
    
    def _queue_alert(self, alert: LocationAlert):
        """
        Queue a generated alert to the alert queue.
        
        Args:
            alert: LocationAlert object
        """
        try:
            success = self.message_queue.push_alert(
                ruta=alert.ruta,
                latitude=alert.latitude,
                longitude=alert.longitude,
                alert_type=alert.alert_type.value,
                area_name=alert.zone_name,
                severity=alert.severity.value
            )
            
            if success:
                logger.warning(
                    f"[ALERT] Route {alert.ruta}: {alert.alert_type.value} "
                    f"in {alert.zone_name} - Severity: {alert.severity.value}"
                )
            else:
                logger.error(f"Failed to queue alert for route {alert.ruta}")
                
        except Exception as e:
            logger.error(f"Error queuing alert: {e}")
    
    def stop(self):
        """Stop the consumer service."""
        logger.info("Stopping Alert Consumer Service...")
        self.is_running = False
        logger.info(
            f"Final statistics - Processed: {self.processed_count}, "
            f"Alerts generated: {self.alert_count}"
        )
    
    def get_stats(self) -> dict:
        """
        Get current consumer statistics.
        
        Returns:
            Dictionary with consumer stats
        """
        return {
            'is_running': self.is_running,
            'coordinates_processed': self.processed_count,
            'alerts_generated': self.alert_count,
            'coordinate_queue_length': self.message_queue.get_queue_length('coordinate_queue'),
            'alert_queue_length': self.message_queue.get_queue_length('alert_queue'),
            'timestamp': datetime.now(ZoneInfo("America/Bogota")).isoformat()
        }

def main():
    """Main entry point for the alert consumer service."""
    consumer = AlertConsumer()
    
    # Start processing with 1-second poll interval
    consumer.start(poll_interval=1)

if __name__ == "__main__":
    main()
