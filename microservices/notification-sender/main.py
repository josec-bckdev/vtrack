import json
import logging
import time
import signal
import sys
from shared.message_queue import MessageQueue
from config import settings
from providers.telegram import TelegramNotifier

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class NotificationConsumer:
    """Consumes alerts from Redis and sends to Telegram"""
    
    def __init__(self):
        self.redis_queue = MessageQueue(redis_url=settings.REDIS_URL)
        
        # Log configuration (mask sensitive data)
        logger.info(f"Redis URL: {settings.REDIS_URL}")
        logger.info(f"Poll Interval: {settings.POLL_INTERVAL}s")
        logger.info(f"Telegram Bot Token: {'*' * 20}{settings.TELEGRAM_BOT_TOKEN[-4:] if len(settings.TELEGRAM_BOT_TOKEN) > 4 else 'NOT SET'}")
        logger.info(f"Telegram Chat ID: {settings.TELEGRAM_CHAT_ID}")
        
        if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
            logger.error("❌ TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set!")
            logger.error("Set them in .env or environment variables")
        
        self.telegram = TelegramNotifier()
        self.running = True
        
        # Stats
        self.processed = 0
        self.start_time = time.time()
    
    def handle_signal(self, signum, frame):
        """Handle shutdown gracefully"""
        logger.info("Shutting down...")
        self.running = False
    
    def run(self):
        """Main loop"""
        logger.info("🚀 Starting VTRACK Notification Service")
        logger.info(f"📱 Sending to chat ID: {self.telegram.chat_id}")
        
        # Send startup notification
        logger.info("📨 Sending test message...")
        self.telegram.send_test()
        logger.info("✅ Test message sent - check your phone!")
        
        while self.running:
            try:
                # Check for alerts
                alert_data = self.redis_queue.pop_alert()
                
                if alert_data:
                    # Send to Telegram
                    success = self.telegram.send_alert(alert_data)
                    
                    if success:
                        self.processed += 1
                        logger.info(f"📊 Total alerts sent: {self.processed}")
                else:
                    # No alerts, wait a bit
                    time.sleep(settings.POLL_INTERVAL)
                    
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Error: {e}")
                time.sleep(5)
        
        # Shutdown stats
        runtime = time.time() - self.start_time
        logger.info("=" * 40)
        logger.info(f"🛑 Service stopped")
        logger.info(f"⏱️  Runtime: {runtime:.0f} seconds")
        logger.info(f"📨 Alerts sent: {self.processed}")
        logger.info("=" * 40)

def main():
    consumer = NotificationConsumer()
    
    # Handle signals
    signal.signal(signal.SIGINT, consumer.handle_signal)
    signal.signal(signal.SIGTERM, consumer.handle_signal)
    
    consumer.run()

if __name__ == "__main__":
    main()