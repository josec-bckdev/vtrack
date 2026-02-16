import logging
import asyncio
from telegram import Bot
from telegram.error import TelegramError
from config import settings, load_users

logger = logging.getLogger(__name__)

class TelegramNotifier:
    """Telegram notification sender with multi-user support"""
    
    def __init__(self):
        logger.info(f"Initializing Telegram bot...")
        logger.info(f"Bot Token length: {len(settings.TELEGRAM_BOT_TOKEN)}")
        
        self.bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        
        # Load users from users.yaml
        try:
            self.users = load_users()
            logger.info(f"✅ Loaded {len(self.users)} users from users.yaml")
            
            # Log user summary
            admin_count = sum(1 for u in self.users if u['role'] == 'admin')
            user_count = sum(1 for u in self.users if u['role'] == 'user')
            logger.info(f"   📊 {admin_count} admin(s), {user_count} regular user(s)")
            
            for user in self.users:
                logger.info(f"   👤 {user['name']} ({user['role']}) - Chat ID: {user['telegram_id']}")
                
        except Exception as e:
            logger.error(f"❌ Failed to load users.yaml: {e}")
            logger.error("Falling back to legacy TELEGRAM_CHAT_ID from environment")
            # Fallback to old single-user mode
            if settings.TELEGRAM_CHAT_ID:
                self.users = [{
                    'name': 'Legacy User',
                    'telegram_id': settings.TELEGRAM_CHAT_ID,
                    'role': 'admin'
                }]
            else:
                raise ValueError("No users configured and TELEGRAM_CHAT_ID not set!")
        
        # Keep chat_id for backward compatibility (uses first user)
        self.chat_id = self.users[0]['telegram_id'] if self.users else None
        
        # ==================== EVENT LOOP PATTERN FOR ASYNC CODE ====================
        #
        # THE PROBLEM WE'RE SOLVING:
        # ==========================
        # The Telegram library (python-telegram-bot) uses ASYNC methods like:
        #     await bot.send_message(...)
        #
        # But our NotificationConsumer runs SYNCHRONOUSLY:
        #     def run(self):         ← Not "async def"
        #         while True:        ← Regular loop, not async
        #             send_alert()   ← Regular method
        #
        # We can't use 'await' in synchronous code! This would fail:
        #     def send_alert(self):
        #         await self.bot.send_message(...)  ← ERROR: 'await' outside async
        #
        # THE SOLUTION - self.loop (Persistent Event Loop):
        # ==================================================
        # We create ONE event loop that lives for the entire lifetime of this object
        # and use it to run async code from sync context.
        #
        # WHY CREATE IT IN __init__?
        # ==========================
        # Creating event loops is expensive. If we created a new loop every time
        # we sent a message, we'd have HUGE overhead:
        #
        # ❌ BAD (what we DON'T do):
        #     def send_alert(self):
        #         loop = asyncio.new_event_loop()        ← Create (expensive!)
        #         loop.run_until_complete(send_message)  ← Run
        #         loop.close()                           ← Destroy
        #     # For 1000 alerts = 1000 loop create/destroy cycles!
        #
        # ✅ GOOD (what we DO):
        #     def __init__(self):
        #         self.loop = asyncio.new_event_loop()   ← Create ONCE
        #     
        #     def send_alert(self):
        #         self.loop.run_until_complete(...)      ← Reuse same loop
        #     # For 1000 alerts = 1 loop creation, reused 1000 times!
        #
        # THE TRY/EXCEPT PATTERN:
        # =======================
        # try:
        #     self.loop = asyncio.get_event_loop()
        #       ↑
        #       Try to get the CURRENT event loop (if one exists)
        #       
        # except RuntimeError:
        #     self.loop = asyncio.new_event_loop()
        #       ↑
        #       No loop exists (or it was closed), create a NEW one
        #     
        #     asyncio.set_event_loop(self.loop)
        #       ↑
        #       Make it the CURRENT loop for this thread
        #
        # WHY THIS PATTERN?
        # =================
        # Different environments have different loop states:
        #
        # Scenario 1: Fresh Python process (most common)
        #   - No event loop exists yet
        #   - get_event_loop() raises RuntimeError
        #   - We create and set a new one
        #
        # Scenario 2: Already in async context (less common)
        #   - Another part of code created a loop
        #   - get_event_loop() returns existing loop
        #   - We reuse it (saves memory!)
        #
        # Scenario 3: Loop was closed (rare but possible)
        #   - Previous loop existed but was closed
        #   - get_event_loop() raises RuntimeError  
        #   - We create fresh one
        #
        # THREAD SAFETY NOTE:
        # ===================
        # Event loops are THREAD-LOCAL (one per thread)
        # Our service is single-threaded, so this is safe
        # If we used threading.Thread, each thread needs its own loop!
        #
        # IMPLICATIONS OF THIS PATTERN:
        # ==============================
        # 1. PERFORMANCE:
        #    - Fast: Reusing loop avoids creation overhead
        #    - Memory efficient: One loop vs. thousands
        #
        # 2. BLOCKING BEHAVIOR:
        #    - run_until_complete() BLOCKS until message sends
        #    - We can't process other alerts while sending
        #    - This is OK for our use case (low-volume alerts)
        #
        # 3. ERROR HANDLING:
        #    - If send fails, loop stays alive (we can retry)
        #    - Loop only dies if we explicitly close it
        #
        # 4. ALTERNATIVE APPROACHES:
        #    A) Make everything async (more complex):
        #        async def run(self):
        #            async def send_alert(self):
        #                await self.bot.send_message(...)
        #       Problem: NotificationConsumer would need async rewrite
        #
        #    B) Use threading (more overhead):
        #        thread = Thread(target=send_message)
        #        thread.start()
        #       Problem: Thread creation overhead, complexity
        #
        #    C) Current approach (sync wrapper around async):
        #        Pros: Simple, efficient, works with sync code
        #        Cons: Blocks during send (acceptable for our volume)
        #
        # WHEN YOU'D USE FULL ASYNC:
        # ==========================
        # If we had HIGH-VOLUME alerts (100s per second), we'd want:
        #     async def send_alert(self, alert):
        #         await self.bot.send_message(...)
        #     
        #     async def run(self):
        #         while True:
        #             alert = await queue.get()
        #             asyncio.create_task(self.send_alert(alert))
        #                    ↑
        #                    Sends happen concurrently!
        #
        # But for LOW-VOLUME (a few per minute), blocking is fine and simpler.
        #
        # KEY TAKEAWAY:
        # =============
        # self.loop = persistent event loop that bridges sync and async worlds
        # Created once, reused many times, makes blocking calls simple and efficient
        
        # Create a persistent event loop for async operations
        try:
            # Try to get existing loop (if another async context created one)
            self.loop = asyncio.get_event_loop()
        except RuntimeError:
            # No loop exists, create a fresh one for this thread
            self.loop = asyncio.new_event_loop()
            # Set it as THE loop for this thread
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
        """
        Send an alert to ALL users (Sync wrapper around async Telegram API)
        
        This method loops through all configured users and sends the alert
        to each recipient. Both admin and regular users receive alerts.
        
        Returns:
            bool: True if at least one message was sent successfully
        """
        success_count = 0
        failure_count = 0
        
        message = self.format_alert(alert_data)
        
        logger.info(f"📤 Sending alert to {len(self.users)} recipient(s)")
        
        for user in self.users:
            try:
                logger.debug(f"   Sending to {user['name']} ({user['telegram_id']})...")
                
                # Run async send_message using the persistent event loop
                result = self.loop.run_until_complete(self.bot.send_message(
                    chat_id=user['telegram_id'],
                    text=message,
                    parse_mode='Markdown'
                ))
                
                logger.info(f"   ✅ Sent to {user['name']} - Message ID: {result.message_id}")
                success_count += 1
                
            except TelegramError as e:
                logger.error(f"   ❌ Telegram error sending to {user['name']}: {e}")
                logger.error(f"      Error type: {type(e).__name__}")
                logger.error(f"      Chat ID: {user['telegram_id']}")
                failure_count += 1
                
            except Exception as e:
                logger.error(f"   ❌ Unexpected error sending to {user['name']}: {e}")
                logger.error(f"      Error type: {type(e).__name__}")
                failure_count += 1
        
        # Summary
        logger.info(f"📊 Alert delivery: {success_count} succeeded, {failure_count} failed")
        
        # Return True if at least one message was sent successfully
        return success_count > 0
    
    def send_test(self):
        """
        Send a test message to ADMIN users only
        
        Regular users don't receive test messages to avoid spam.
        Only users with role='admin' will receive the test notification.
        
        Returns:
            bool: True if at least one admin received the message
        """
        logger.info("📨 Preparing test message...")
        
        # Filter for admin users only
        admin_users = [u for u in self.users if u['role'] == 'admin']
        
        if not admin_users:
            logger.warning("⚠️  No admin users found! Test message not sent.")
            logger.warning("   Add at least one user with role='admin' in users.yaml")
            return False
        
        logger.info(f"🎯 Sending test message to {len(admin_users)} admin(s)")
        
        test_alert = {
            'ruta': 101,
            'alert_type': 'GEOFENCE_ENTRY',
            'area_name': 'Test Zone',
            'severity': 'INFO',
            'latitude': 4.7110,
            'longitude': -74.0059,
            'timestamp': '2024-01-01 12:00:00'
        }
        
        success_count = 0
        failure_count = 0
        
        message = self.format_alert(test_alert)
        
        for user in admin_users:
            try:
                logger.debug(f"   Sending test to {user['name']} ({user['telegram_id']})...")
                
                result = self.loop.run_until_complete(self.bot.send_message(
                    chat_id=user['telegram_id'],
                    text=f"🧪 *TEST MESSAGE*\n\n{message}",
                    parse_mode='Markdown'
                ))
                
                logger.info(f"   ✅ Test sent to {user['name']} - Message ID: {result.message_id}")
                success_count += 1
                
            except TelegramError as e:
                logger.error(f"   ❌ Telegram error sending to {user['name']}: {e}")
                failure_count += 1
                
            except Exception as e:
                logger.error(f"   ❌ Unexpected error sending to {user['name']}: {e}")
                failure_count += 1
        
        # Summary
        if success_count > 0:
            logger.info(f"✅ Test message sent successfully to {success_count}/{len(admin_users)} admin(s)")
        else:
            logger.error(f"❌ Test message failed for all {len(admin_users)} admin(s)")
        
        return success_count > 0