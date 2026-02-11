#!/usr/bin/env python3
"""
Redis Queue Monitor - Real-time monitoring of VTrack message queues

Usage:
    python redis_monitor.py                    # Monitor with default settings
    python redis_monitor.py --interval 1       # Update every 1 second
    python redis_monitor.py --peek 5           # Show 5 items from each queue
"""

import redis
import json
import time
import sys
import argparse
from datetime import datetime
from typing import Optional


class RedisQueueMonitor:
    """Monitor Redis queues in real-time"""

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        """Initialize connection to Redis"""
        try:
            self.redis = redis.from_url(redis_url, decode_responses=True)
            self.redis.ping()
            print(f"✅ Connected to Redis at {redis_url}\n")
        except Exception as e:
            print(f"❌ Failed to connect to Redis: {e}")
            print("\n💡 Make sure Redis is running:")
            print("   docker ps | grep redis")
            print("   docker start redis_queue")
            sys.exit(1)

    def get_queue_stats(self) -> dict:
        """Get statistics about all queues"""
        return {
            'coordinate_queue_length': self.redis.llen('coordinate_queue'),
            'alert_queue_length': self.redis.llen('alert_queue'),
            'memory_used': self.redis.info('memory')['used_memory_human'],
            'connected_clients': self.redis.info('clients')['connected_clients'],
            'total_commands': self.redis.info('stats')['total_commands_processed'],
        }

    def peek_coordinate(self, index: int = -1) -> Optional[dict]:
        """Peek at a coordinate in the queue (default: next to be processed)"""
        try:
            data = self.redis.lindex('coordinate_queue', index)
            return json.loads(data) if data else None
        except Exception as e:
            print(f"⚠️  Error peeking coordinate: {e}")
            return None

    def peek_alert(self, index: int = 0) -> Optional[dict]:
        """Peek at an alert in the queue (default: most recent)"""
        try:
            data = self.redis.lindex('alert_queue', index)
            return json.loads(data) if data else None
        except Exception as e:
            print(f"⚠️  Error peeking alert: {e}")
            return None

    def get_recent_coordinates(self, count: int = 5) -> list:
        """Get the N most recent coordinates (front of queue)"""
        try:
            items = self.redis.lrange('coordinate_queue', 0, count - 1)
            return [json.loads(item) for item in items]
        except Exception as e:
            print(f"⚠️  Error getting recent coordinates: {e}")
            return []

    def get_recent_alerts(self, count: int = 5) -> list:
        """Get the N most recent alerts (front of queue)"""
        try:
            items = self.redis.lrange('alert_queue', 0, count - 1)
            return [json.loads(item) for item in items]
        except Exception as e:
            print(f"⚠️  Error getting recent alerts: {e}")
            return []

    def display_stats(self, stats: dict, clear_screen: bool = True):
        """Display queue statistics"""
        if clear_screen:
            # Clear screen (works on Linux/Mac/Windows)
            print("\033[2J\033[H", end="")

        print("=" * 80)
        print(f"🔍 VTrack Redis Queue Monitor - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        print()
        print(f"📊 Queue Lengths:")
        print(f"   • Coordinate Queue: {stats['coordinate_queue_length']:,} items")
        print(f"   • Alert Queue:      {stats['alert_queue_length']:,} items")
        print()
        print(f"💾 Redis Status:")
        print(f"   • Memory Used:      {stats['memory_used']}")
        print(f"   • Connected Clients: {stats['connected_clients']}")
        print(f"   • Commands Processed: {stats['total_commands']:,}")
        print()

    def display_coordinate_preview(self, coords: list):
        """Display preview of coordinates"""
        if not coords:
            print("📍 Coordinate Queue: Empty")
            return

        print(f"📍 Coordinate Queue Preview (showing {len(coords)} newest):")
        print("-" * 80)
        for i, coord in enumerate(coords, 1):
            ruta = coord.get('ruta', 'N/A')
            lat = coord.get('latitude', 0)
            lon = coord.get('longitude', 0)
            queued = coord.get('queued_at', 'N/A')
            status = coord.get('route_status', 'N/A')
            print(f"   {i}. Ruta {ruta:>3} | ({lat:>7.4f}, {lon:>8.4f}) | {status:>15} | {queued[:19]}")
        print()

    def display_alert_preview(self, alerts: list):
        """Display preview of alerts"""
        if not alerts:
            print("🚨 Alert Queue: Empty")
            return

        print(f"🚨 Alert Queue Preview (showing {len(alerts)} newest):")
        print("-" * 80)
        for i, alert in enumerate(alerts, 1):
            ruta = alert.get('ruta', 'N/A')
            alert_type = alert.get('alert_type', 'N/A')
            area = alert.get('area_name', 'N/A')
            severity = alert.get('severity', 'N/A')

            # Color code severity
            severity_icon = {
                'INFO': '💡',
                'WARNING': '⚠️',
                'CRITICAL': '🔥'
            }.get(severity, '❓')

            print(f"   {i}. {severity_icon} Ruta {ruta:>3} | {alert_type:>20} | {area:>20} | {severity}")
        print()

    def monitor(self, interval: int = 2, peek_count: int = 5, clear_screen: bool = True):
        """Monitor queues continuously"""
        print(f"🚀 Starting monitor (updating every {interval}s, showing {peek_count} items)")
        print("   Press Ctrl+C to stop\n")
        time.sleep(1)

        try:
            while True:
                # Get stats
                stats = self.get_queue_stats()

                # Display stats
                self.display_stats(stats, clear_screen)

                # Get and display coordinates
                coords = self.get_recent_coordinates(peek_count)
                self.display_coordinate_preview(coords)

                # Get and display alerts
                alerts = self.get_recent_alerts(peek_count)
                self.display_alert_preview(alerts)

                print("-" * 80)
                print(f"Next update in {interval}s... (Press Ctrl+C to stop)")

                time.sleep(interval)

        except KeyboardInterrupt:
            print("\n\n👋 Monitoring stopped. Goodbye!")
            sys.exit(0)

    def show_snapshot(self, peek_count: int = 5):
        """Show a single snapshot of the queues"""
        stats = self.get_queue_stats()
        self.display_stats(stats, clear_screen=False)

        coords = self.get_recent_coordinates(peek_count)
        self.display_coordinate_preview(coords)

        alerts = self.get_recent_alerts(peek_count)
        self.display_alert_preview(alerts)


def main():
    parser = argparse.ArgumentParser(
        description="Monitor VTrack Redis message queues in real-time"
    )
    parser.add_argument(
        '--redis-url',
        default='redis://localhost:6379/0',
        help='Redis connection URL (default: redis://localhost:6379/0)'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=2,
        help='Update interval in seconds (default: 2)'
    )
    parser.add_argument(
        '--peek',
        type=int,
        default=5,
        help='Number of items to show from each queue (default: 5)'
    )
    parser.add_argument(
        '--snapshot',
        action='store_true',
        help='Show a single snapshot instead of continuous monitoring'
    )
    parser.add_argument(
        '--no-clear',
        action='store_true',
        help='Don\'t clear screen between updates'
    )

    args = parser.parse_args()

    # Create monitor
    monitor = RedisQueueMonitor(args.redis_url)

    # Run in snapshot or continuous mode
    if args.snapshot:
        monitor.show_snapshot(args.peek)
    else:
        monitor.monitor(
            interval=args.interval,
            peek_count=args.peek,
            clear_screen=not args.no_clear
        )


if __name__ == "__main__":
    main()
