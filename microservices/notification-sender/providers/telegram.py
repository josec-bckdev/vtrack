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
        Send an alert to Telegram (Sync wrapper around async Telegram API)
        
        HOW THIS CONNECTS TO self.loop:
        ================================
        Remember: self.loop was created in __init__ and lives for entire object lifetime
        
        THE KEY LINE:
        =============
        result = self.loop.run_until_complete(self.bot.send_message(...))
                 ↑             ↑               ↑
                 |             |               The async coroutine (not executed yet)
                 |             Blocks until coroutine completes
                 Our persistent event loop
        
        WHAT HAPPENS STEP-BY-STEP:
        ==========================
        1. self.bot.send_message() returns a COROUTINE object
           - It's like a "promise to do async work"
           - Nothing executes yet! Just a recipe waiting to run
        
        2. self.loop.run_until_complete() takes that coroutine and:
           a) Schedules it on the event loop
           b) Runs the event loop (starts processing)
           c) BLOCKS this thread until send_message finishes
           d) Returns the result (the sent Message object)
        
        3. During the block (step c), here's what happens:
           - Telegram library opens HTTP connection
           - Sends POST request to Telegram API
           - Waits for response (network I/O)
           - Parses response
           - Returns Message object
        
        BLOCKING VISUALIZATION:
        =======================
        Timeline of execution:
        
        Time  | Main Thread                    | Network Activity
        ------|--------------------------------|------------------
        T0    | send_alert() called           | 
        T1    | Format message                 | 
        T2    | loop.run_until_complete()     | Opens connection
        T3    | ⏸️ BLOCKED waiting...          | Sending HTTP request
        T4    | ⏸️ Still waiting...            | Server processing
        T5    | ⏸️ Still waiting...            | Receiving response
        T6    | ✅ Unblocks, gets result       | Connection closes
        T7    | Log success message            |
        T8    | return True                    |
        
        During T3-T5, the main thread cannot:
        - Process other alerts
        - Check for new alerts
        - Do ANY other work (it's BLOCKED)
        
        WHY IS THIS OK?
        ===============
        For our use case (low-volume alerts):
        - Send takes ~100-500ms
        - We get 1-2 alerts per minute
        - Blocking for 500ms is negligible
        
        When it would be BAD:
        - High volume: 100 alerts/second
        - 500ms block × 100 = can only handle 2 per second!
        - Would need full async: await send_message() + task concurrency
        
        ALTERNATIVE 1 - Full Async (High Volume):
        ==========================================
        async def send_alert(self, alert_data):
            result = await self.bot.send_message(...)
                     ↑
                     Yields control to event loop while waiting
                     Other coroutines can run concurrently
        
        async def main_loop():
            while True:
                alert = await pop_from_queue()
                asyncio.create_task(send_alert(alert))  ← Non-blocking!
                         ↑
                         Schedules send, doesn't wait for completion
        
        Pros: Can send 100s of messages concurrently
        Cons: Entire codebase becomes async (complex refactor)
        
        ALTERNATIVE 2 - Threading (Medium Volume):
        ===========================================
        def send_alert(self, alert_data):
            thread = Thread(target=self._send_sync, args=(alert_data,))
            thread.start()  ← Non-blocking
        
        def _send_sync(self, alert_data):
            loop = asyncio.new_event_loop()
            loop.run_until_complete(self.bot.send_message(...))
            loop.close()
        
        Pros: Non-blocking, keeps sync code
        Cons: Thread overhead, no easy way to track results
        
        ALTERNATIVE 3 - Current Approach (Low Volume):
        ===============================================
        def send_alert(self, alert_data):
            result = self.loop.run_until_complete(...)  ← Blocking
        
        Pros: Simple, efficient, easy to debug, predictable
        Cons: Blocks during send (acceptable at low volume)
        
        WHEN TO MIGRATE TO FULL ASYNC:
        ===============================
        Signs you need it:
        1. Alerts queue up faster than you can send
        2. LLEN alert_queue keeps growing
        3. Alert latency > 5 seconds
        4. You see "slow sending" logs
        
        Until then, this pattern is PERFECT for the job:
        - Simple to understand
        - Easy to debug (sequential execution)
        - Efficient enough for current load
        - No concurrency bugs to worry about
        
        IMPORTANT: WHY run_until_complete() NOT await():
        =================================================
        This won't work:
            def send_alert(self):
                result = await self.bot.send_message(...)
                         ↑
                         SyntaxError: 'await' outside async function
        
        'await' can ONLY be used inside 'async def' functions
        We're in regular 'def', so we use run_until_complete() instead
        
        Think of it as:
            await              → async world's way to wait
            run_until_complete → sync world's way to wait for async
        """
        try:
            message = self.format_alert(alert_data)
            logger.info(f"📤 Sending message to chat_id: {self.chat_id}")
            logger.debug(f"Message content: {message}")
            
            # ==================== THE MAGIC LINE ====================
            # Run async send_message using the persistent event loop
            # 
            # What happens:
            # 1. bot.send_message() creates a coroutine (async task definition)
            # 2. loop.run_until_complete() executes it on our persistent loop
            # 3. This thread BLOCKS until Telegram API responds
            # 4. Result is returned (Message object from Telegram)
            #
            # Blocking duration: Usually 100-500ms (network + Telegram processing)
            # 
            # During this time, the main consumer loop is PAUSED at this line
            # Can't process other alerts until this returns
            # Trade-off: Simplicity vs. Concurrency (we chose simplicity)
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