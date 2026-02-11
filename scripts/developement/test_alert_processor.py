#!/usr/bin/env python3
"""
Test script for alert-processor development

This script helps you test the alert-processor by:
1. Pushing test coordinates to Redis
2. Watching them get processed
3. Checking generated alerts

Usage:
    python test_alert_processor.py                    # Single test coordinate
    python test_alert_processor.py --scenario zone    # Test geofence entry
    python test_alert_processor.py --scenario batch   # Test batch processing
    python test_alert_processor.py --load 100         # Load test with 100 coordinates
"""

import redis
import json
import time
import argparse
from datetime import datetime
from zoneinfo import ZoneInfo


class AlertProcessorTester:
    """Helper class to test alert-processor functionality"""

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        """Initialize Redis connection"""
        try:
            self.redis = redis.from_url(redis_url, decode_responses=True)
            self.redis.ping()
            print(f"✅ Connected to Redis at {redis_url}\n")
        except Exception as e:
            print(f"❌ Failed to connect to Redis: {e}")
            print("\n💡 Make sure Redis is running:")
            print("   docker ps | grep redis")
            exit(1)

    def push_coordinate(self, ruta: int, latitude: float, longitude: float,
                       route_status: str = "En Servicio",
                       student_status: str = "Activo") -> bool:
        """Push a test coordinate to the queue"""
        coordinate = {
            "ruta": ruta,
            "latitude": latitude,
            "longitude": longitude,
            "position_ts": datetime.now(ZoneInfo("America/Bogota")).isoformat(),
            "route_status": route_status,
            "student_status": student_status,
            "queued_at": datetime.now(ZoneInfo("America/Bogota")).isoformat()
        }

        try:
            self.redis.lpush('coordinate_queue', json.dumps(coordinate))
            print(f"✅ Pushed: Ruta {ruta} at ({latitude:.4f}, {longitude:.4f})")
            return True
        except Exception as e:
            print(f"❌ Failed to push coordinate: {e}")
            return False

    def get_queue_length(self, queue_name: str) -> int:
        """Get current queue length"""
        return self.redis.llen(queue_name)

    def get_latest_alert(self) -> dict:
        """Get the most recent alert without removing it"""
        try:
            alert_json = self.redis.lindex('alert_queue', 0)
            return json.loads(alert_json) if alert_json else None
        except Exception as e:
            print(f"⚠️  Error getting alert: {e}")
            return None

    def wait_for_processing(self, initial_length: int, timeout: int = 10):
        """Wait for coordinate to be processed"""
        print(f"⏳ Waiting for processing (timeout: {timeout}s)...", end='', flush=True)
        start_time = time.time()

        while time.time() - start_time < timeout:
            current_length = self.get_queue_length('coordinate_queue')
            if current_length < initial_length:
                elapsed = time.time() - start_time
                print(f" Done! ({elapsed:.1f}s)")
                return True
            print('.', end='', flush=True)
            time.sleep(0.5)

        print(" Timeout!")
        return False

    def scenario_single_coordinate(self):
        """Test: Push a single coordinate"""
        print("=" * 70)
        print("📍 SCENARIO: Single Coordinate Test")
        print("=" * 70)

        initial_len = self.get_queue_length('coordinate_queue')
        print(f"Initial queue length: {initial_len}")

        # Push a coordinate (not in any zone)
        self.push_coordinate(
            ruta=101,
            latitude=4.6500,
            longitude=-74.0900
        )

        # Wait for processing
        self.wait_for_processing(initial_len + 1)

        # Check queue
        final_len = self.get_queue_length('coordinate_queue')
        print(f"Final queue length: {final_len}")
        print(f"✅ Coordinate processed: {initial_len + 1} → {final_len}")

    def scenario_geofence_entry(self):
        """Test: Trigger a geofence entry alert"""
        print("=" * 70)
        print("🚨 SCENARIO: Geofence Entry Alert Test")
        print("=" * 70)

        print("\n📋 Default zones:")
        print("  1. School Zone:    (4.7110, -74.0059) radius: 500m")
        print("  2. Dangerous Area: (4.6289, -74.0832) radius: 1000m")
        print("  3. Route Depot:    (4.5500, -74.1000) radius: 750m")

        initial_alerts = self.get_queue_length('alert_queue')
        print(f"\nInitial alerts in queue: {initial_alerts}")

        # Push route outside zones
        print("\n1️⃣ First: Push coordinate OUTSIDE zones (no alert expected)")
        self.push_coordinate(
            ruta=101,
            latitude=4.8000,  # Far from all zones
            longitude=-74.2000
        )
        time.sleep(2)

        # Push route inside School Zone
        print("\n2️⃣ Second: Push coordinate INSIDE School Zone (alert expected!)")
        self.push_coordinate(
            ruta=101,
            latitude=4.7110,  # School Zone center
            longitude=-74.0059
        )

        # Wait for processing
        time.sleep(3)

        # Check alerts
        final_alerts = self.get_queue_length('alert_queue')
        print(f"\nFinal alerts in queue: {final_alerts}")

        if final_alerts > initial_alerts:
            print(f"✅ Alert generated! ({final_alerts - initial_alerts} new alerts)")

            # Show the alert
            alert = self.get_latest_alert()
            if alert:
                print("\n🚨 Latest Alert:")
                print(f"   Ruta: {alert.get('ruta')}")
                print(f"   Type: {alert.get('alert_type')}")
                print(f"   Area: {alert.get('area_name')}")
                print(f"   Severity: {alert.get('severity')}")
                print(f"   Timestamp: {alert.get('timestamp')}")
        else:
            print("⚠️  No alert generated. Check alert-processor logs:")
            print("   docker logs alert_processor | tail -20")

    def scenario_batch_processing(self):
        """Test: Process multiple coordinates in batch"""
        print("=" * 70)
        print("📦 SCENARIO: Batch Processing Test")
        print("=" * 70)

        batch_size = 10
        print(f"Pushing {batch_size} coordinates...")

        initial_len = self.get_queue_length('coordinate_queue')

        # Push batch
        for i in range(batch_size):
            self.push_coordinate(
                ruta=100 + i,
                latitude=4.6500 + (i * 0.01),
                longitude=-74.0900 + (i * 0.01)
            )

        final_len = self.get_queue_length('coordinate_queue')
        print(f"\nQueue length: {initial_len} → {final_len}")
        print(f"Added {final_len - initial_len} coordinates")

        # Wait for processing
        print("\n⏳ Waiting for batch to be processed...")
        timeout = 20
        start_time = time.time()

        while time.time() - start_time < timeout:
            current_len = self.get_queue_length('coordinate_queue')
            processed = (final_len - current_len)
            progress = (processed / batch_size) * 100 if batch_size > 0 else 0

            print(f"\rProcessed: {processed}/{batch_size} ({progress:.0f}%)", end='', flush=True)

            if current_len == initial_len:
                print("\n✅ All coordinates processed!")
                break

            time.sleep(1)
        else:
            print("\n⚠️  Timeout - some coordinates may still be processing")

    def scenario_load_test(self, count: int = 100):
        """Test: Load test with many coordinates"""
        print("=" * 70)
        print(f"⚡ SCENARIO: Load Test ({count} coordinates)")
        print("=" * 70)

        print(f"Pushing {count} coordinates as fast as possible...")

        start_time = time.time()
        for i in range(count):
            lat = 4.6000 + (i % 100) * 0.001
            lon = -74.0000 + (i % 100) * 0.001
            self.push_coordinate(ruta=i % 10 + 100, latitude=lat, longitude=lon)

        push_time = time.time() - start_time
        print(f"✅ Pushed {count} coordinates in {push_time:.2f}s ({count/push_time:.0f} coords/sec)")

        # Monitor processing
        print("\n⏳ Monitoring processing rate...")
        initial_len = self.get_queue_length('coordinate_queue')

        for _ in range(10):  # Monitor for 10 seconds
            time.sleep(1)
            current_len = self.get_queue_length('coordinate_queue')
            processed = initial_len - current_len
            rate = processed / 1.0 if processed > 0 else 0
            print(f"Queue: {current_len:>4} | Processed: {processed:>4} | Rate: {rate:.1f} coords/sec")
            initial_len = current_len

    def check_consumer_status(self):
        """Check if alert-processor is running and healthy"""
        print("=" * 70)
        print("🔍 CONSUMER STATUS CHECK")
        print("=" * 70)

        # Check queues
        coord_len = self.get_queue_length('coordinate_queue')
        alert_len = self.get_queue_length('alert_queue')

        print(f"Coordinate Queue: {coord_len} items")
        print(f"Alert Queue:      {alert_len} items")

        # Check Redis memory
        try:
            info = self.redis.info('memory')
            print(f"Redis Memory:     {info['used_memory_human']}")
        except:
            pass

        print("\n💡 To check if consumer is running:")
        print("   docker ps | grep alert_processor")
        print("\n💡 To view consumer logs:")
        print("   docker logs -f alert_processor")


def main():
    parser = argparse.ArgumentParser(
        description="Test alert-processor functionality"
    )
    parser.add_argument(
        '--redis-url',
        default='redis://localhost:6379/0',
        help='Redis connection URL'
    )
    parser.add_argument(
        '--scenario',
        choices=['single', 'zone', 'batch', 'status'],
        default='single',
        help='Test scenario to run'
    )
    parser.add_argument(
        '--load',
        type=int,
        metavar='N',
        help='Run load test with N coordinates'
    )

    args = parser.parse_args()

    # Create tester
    tester = AlertProcessorTester(args.redis_url)

    # Run scenario
    if args.load:
        tester.scenario_load_test(args.load)
    elif args.scenario == 'single':
        tester.scenario_single_coordinate()
    elif args.scenario == 'zone':
        tester.scenario_geofence_entry()
    elif args.scenario == 'batch':
        tester.scenario_batch_processing()
    elif args.scenario == 'status':
        tester.check_consumer_status()

    print("\n" + "=" * 70)
    print("✅ Test completed!")
    print("=" * 70)


if __name__ == "__main__":
    main()
