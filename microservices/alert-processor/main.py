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

from opentelemetry import trace
from tracing import configure_tracing
from shared.message_queue import MessageQueue
from shared.location_alerts import LocationAnalyzer, LocationAlert

_tracer = trace.get_tracer(__name__)

POLL_INTERVAL_SECONDS = 7  # Time to wait between queue checks

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
    
    def start(self, poll_interval: int = POLL_INTERVAL_SECONDS):
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
                ruta = coordinate.get('ruta')
                latitude = coordinate.get('latitude')
                longitude = coordinate.get('longitude')

                if not all([ruta, latitude, longitude]):
                    logger.warning(f"Invalid coordinate data: {coordinate}")
                    return

                with _tracer.start_as_current_span("alert_processor.coordinate.process") as span:
                    span.set_attribute("coordinate.ruta", ruta)
                    span.set_attribute("coordinate.latitude", latitude)
                    span.set_attribute("coordinate.longitude", longitude)

                    alerts = self.location_analyzer.analyze_coordinate(
                        ruta=ruta,
                        latitude=latitude,
                        longitude=longitude
                    )

                    span.set_attribute("alerts.generated", len(alerts))
                    self.processed_count += 1

                    for alert in alerts:
                        self._queue_alert(alert)
                        self.alert_count += 1

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
            with _tracer.start_as_current_span("alert_processor.alert.queue") as span:
                span.set_attribute("alert.type", alert.alert_type.value)
                span.set_attribute("alert.zone", alert.zone_name)

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
    otlp_endpoint = os.getenv("OTLP_ENDPOINT", "")
    if otlp_endpoint:
        configure_tracing("alert-processor", otlp_endpoint)
        logger.info("OTel tracing configured — exporting to %s", otlp_endpoint)

    consumer = AlertConsumer()
    
    # Start processing with 1-second poll interval
    consumer.start(poll_interval=POLL_INTERVAL_SECONDS)

if __name__ == "__main__":
    main()
