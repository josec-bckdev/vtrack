import logging
import asyncio
from telegram import Bot
from telegram.error import TelegramError
from config import settings

logger = logging.getLogger(__name__)

class TelegramNotifier:
    """Simple Telegram notification sender"""
    
    def __init__(self):
        logger.info(f"Initializing Telegram bot...")
        logger.info(f"Bot Token length: {len(settings.TELEGRAM_BOT_TOKEN)}")
        logger.info(f"Chat ID: {settings.TELEGRAM_CHAT_ID}")
        
        self.bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        self.chat_id = settings.TELEGRAM_CHAT_ID
        
        # Create a persistent event loop for async operations
        try:
            self.loop = asyncio.get_event_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
        
        logger.info("✅ Telegram bot initialized")
    
    def format_alert(self, alert_data):
        """Format an alert into a nice message"""
        # Emoji mapping
        icons = {
            "GEOFENCE_ENTRY": "🚌➡️",
            "GEOFENCE_EXIT": "🚌⬅️",
            "WARNING": "⚠️",
            "CRITICAL": "🚨",
            "INFO": "ℹ️"
        }
        
        alert_type = alert_data.get('alert_type', 'ALERT')
        severity = alert_data.get('severity', 'INFO')
        
        # Get emoji or use default
        main_icon = icons.get(alert_type, "🔔")
        severity_icon = icons.get(severity, "ℹ️")
        
        # Format coordinates for Google Maps
        lat = alert_data.get('latitude', 0)
        lng = alert_data.get('longitude', 0)
        maps_url = f"https://maps.google.com/?q={lat},{lng}"
        
        message = f"""
{severity_icon} *VTRACK ALERT* {main_icon}

*Route:* {alert_data.get('ruta', 'N/A')}
*Event:* {alert_data.get('alert_type', 'N/A').replace('_', ' ')}
*Zone:* {alert_data.get('area_name', 'N/A')}
*Time:* {alert_data.get('timestamp', 'N/A')}

📍 [View on Map]({maps_url})
        """.strip()
        
        return message
    
    def send_alert(self, alert_data):
        """Send an alert to Telegram"""
        try:
            message = self.format_alert(alert_data)
            logger.info(f"📤 Sending message to chat_id: {self.chat_id}")
            logger.debug(f"Message content: {message}")
            
            # Run async send_message using the persistent event loop
            result = self.loop.run_until_complete(self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='Markdown'
            ))
            logger.info(f"✅ Sent alert for route {alert_data.get('ruta')} - Message ID: {result.message_id}")
            return True
        except TelegramError as e:
            logger.error(f"❌ Telegram error: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Chat ID used: {self.chat_id}")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            return False
    
    def send_test(self):
        """Send a test message"""
        logger.info("📨 Preparing test message...")
        test_alert = {
            'ruta': 101,
            'alert_type': 'GEOFENCE_ENTRY',
            'area_name': 'Test Zone',
            'severity': 'INFO',
            'latitude': 4.7110,
            'longitude': -74.0059,
            'timestamp': '2024-01-01 12:00:00'
        }
        result = self.send_alert(test_alert)
        if result:
            logger.info("✅ Test message sent successfully")
        else:
            logger.error("❌ Test message failed")
        return result