"""
VTRACK Notification Sender Microservice

This microservice consumes geofence alerts from Redis and sends real-time
notifications to designated channels (Telegram, SMS, etc.).

Architecture:
    - Consumes from: Redis alert_queue (FIFO)
    - Sends to: Telegram Bot API (extensible to other providers)
    - Runs independently: Can be scaled horizontally

Responsibilities:
    - Poll alert_queue for new geofence alerts
    - Format alert messages for human readability
    - Send notifications via configured providers
    - Track delivery metrics (success/failure rates)
    - Handle graceful shutdown and cleanup

Flow:
    1. Poll Redis alert_queue with configurable interval
    2. Parse LocationAlert data (ruta, zone, alert_type, severity)
    3. Format message with emoji indicators and severity context
    4. Send via Telegram (or other configured providers)
    5. Log delivery status and update metrics
    6. Sleep and repeat

Environment Variables:
    - REDIS_URL: Redis connection string (default: redis://localhost:6379/0)
    - TELEGRAM_BOT_TOKEN: Bot token from @BotFather
    - TELEGRAM_CHAT_ID: Target chat/channel ID
    - POLL_INTERVAL: Seconds between queue checks (default: 2)

Usage:
    docker-compose up notification-sender
    
    # Or standalone:
    python main.py
"""

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
        """
        Handle shutdown signals gracefully (SIGINT, SIGTERM)
        
        WHY DO WE NEED THIS?
        =====================
        When you want to stop a running program, the OS sends "signals" (interrupts).
        Without a handler, the program dies IMMEDIATELY - no cleanup, no goodbye message.
        
        With a signal handler, we can:
        - Log that we're shutting down
        - Finish processing current alert (don't cut off mid-send)
        - Send final statistics
        - Close connections cleanly
        - Exit gracefully instead of crashing
        
        HOW IT WORKS:
        =============
        1. OS sends signal (SIGINT or SIGTERM) to our process
        2. Python interrupts the current code execution
        3. Calls this function with signal info
        4. We set self.running = False
        5. The while loop in run() checks self.running and exits cleanly
        6. Cleanup code after the loop runs (stats, logs)
        
        PARAMETERS:
        -----------
        signum : int
            Signal number (e.g., 2=SIGINT, 15=SIGTERM)
            You can check which signal triggered: if signum == signal.SIGINT...
        
        frame : frame object
            Current stack frame (where in code we were when interrupted)
            Usually not needed, but available for debugging
        
        REAL-WORLD EXAMPLE:
        -------------------
        Without handler:
            $ docker stop notification-sender
            → Process KILLED instantly, mid-message send
            → No logs, no stats, connection left open
            → Exit code: 137 (killed by signal)
        
        With handler:
            $ docker stop notification-sender
            → Signal caught by handle_signal()
            → Finishes current alert send
            → Logs shutdown stats
            → Exit code: 0 (clean exit)
        """
        logger.info(f"⚠️  Received shutdown signal ({signum})")
        logger.info("Finishing current task and shutting down...")
        self.running = False
    
    def run(self):
        """Main loop"""
        logger.info("🚀 Starting VTRACK Notification Service")
        logger.info(f"📱 Sending to chat ID: {self.telegram.chat_id}")
        
        # Send startup notification
        logger.info("📨 Sending test message...")
        self.telegram.send_test()
        logger.info("✅ Test message sent - check your phone!")
        
        # ==================== MAIN PROCESSING LOOP ====================
        # 
        # HOW SIGNAL HANDLER CONNECTS TO THIS LOOP:
        # ==========================================
        # This loop checks: while self.running:
        #                          ↑
        #                          This flag!
        # 
        # Normal operation: self.running = True → loop continues forever
        # 
        # When signal arrives:
        #   1. Signal handler sets: self.running = False
        #   2. Current iteration finishes (sends current alert)
        #   3. Loop checks condition: while False → exits
        #   4. Cleanup code after loop runs
        #
        # This is called "cooperative shutdown" - the loop cooperates by
        # checking a flag instead of being forcefully killed.
        #
        # Why not just exit() in the handler?
        #   - exit() would stop IMMEDIATELY, possibly mid-send
        #   - Setting flag lets current work finish cleanly
        #   - Cleanup code gets to run (stats, close connections)
        #
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
                # NOTE: This is belt-and-suspenders error handling
                # The signal handler SHOULD catch Ctrl+C (SIGINT) and set self.running=False
                # But if something goes wrong with signal handling, this catches it too
                # Good practice: handle both signal AND exception for robustness
                logger.warning("KeyboardInterrupt caught (signal handler also running)")
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
    
    # ==================== SIGNAL HANDLER REGISTRATION ====================
    # 
    # WHAT IS signal.signal()?
    # ========================
    # This is Python's way of saying: "When the OS sends signal X, call function Y"
    # 
    # Syntax: signal.signal(SIGNAL_TYPE, handler_function)
    #         - SIGNAL_TYPE: Which interrupt to catch
    #         - handler_function: Your function to call (must accept signum, frame)
    #
    # COMMON SIGNALS:
    # ===============
    # SIGINT (signal 2):  Ctrl+C in terminal
    #                     What happens: User presses Ctrl+C → OS sends SIGINT
    #                     
    # SIGTERM (signal 15): Graceful shutdown request
    #                      What happens: docker stop → Docker sends SIGTERM first
    #                                   systemctl stop → systemd sends SIGTERM
    #                                   kill <pid> → Sends SIGTERM by default
    #
    # SIGKILL (signal 9):  FORCE kill (cannot be caught!)
    #                      docker kill / kill -9 → Process dies instantly
    #                      No handler can catch this - it's the nuclear option
    #
    # WHY REGISTER BOTH SIGINT AND SIGTERM?
    # ======================================
    # - SIGINT: Handles local development (Ctrl+C)
    # - SIGTERM: Handles production deployment (docker stop, systemctl)
    # 
    # Docker shutdown sequence:
    #   1. docker stop → sends SIGTERM
    #   2. Waits 10 seconds for graceful shutdown
    #   3. If still running → sends SIGKILL (unstoppable)
    #
    # WHAT HAPPENS WHEN SIGNAL ARRIVES:
    # ==================================
    # Before registration:
    #   Ctrl+C → Python default handler → raises KeyboardInterrupt → stack unwinds
    #   docker stop → SIGTERM → Process exits immediately with code 143
    #
    # After registration:
    #   Ctrl+C → OS sends SIGINT → consumer.handle_signal() called
    #        → self.running = False
    #        → while loop exits
    #        → cleanup code runs
    #        → exit code 0
    #
    # EXAMPLE FLOW:
    # =============
    # 1. Service running: while self.running: ...
    # 2. You press Ctrl+C in terminal
    # 3. OS sends SIGINT to Python process
    # 4. Python looks up: "What function handles SIGINT?"
    # 5. Finds: consumer.handle_signal
    # 6. Calls: consumer.handle_signal(signum=2, frame=<current_stack>)
    # 7. Handler sets: self.running = False
    # 8. Current loop iteration finishes
    # 9. Loop checks: if self.running → False → exits
    # 10. Cleanup code runs (stats, logs)
    # 11. Program exits cleanly
    #
    # IMPORTANT NOTES:
    # ================
    # - Handler MUST be fast! Don't do heavy work here
    # - Handler interrupts your code at ANY point (even mid-line!)
    # - Multiple signals → handler called multiple times (we just set flag)
    # - Can't catch SIGKILL (9) or SIGSTOP (19) - OS reserves these
    #
    # TESTING:
    # ========
    # Local: python main.py → press Ctrl+C → see graceful shutdown
    # Docker: docker stop notification-sender → see graceful shutdown
    # Force: docker kill notification-sender → instant death (no handler runs)
    
    signal.signal(signal.SIGINT, consumer.handle_signal)   # Catch Ctrl+C
    signal.signal(signal.SIGTERM, consumer.handle_signal)  # Catch docker stop
    
    consumer.run()

if __name__ == "__main__":
    main()