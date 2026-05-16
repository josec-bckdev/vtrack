import logging
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from fastapi import FastAPI, HTTPException
from app.database import init_db
from .data_server import router as data_server_router
from app.scraper_async import collection_manager
from app.models import CollectionStatusResponse, CollectionStatusEnum
from shared.message_queue import MessageQueue
import os

from app.cookie_refresh import run_refresh

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Scheduler:
    """Manages scheduled collection and cookie-refresh tasks."""

    def __init__(self):
        self.morning_task: asyncio.Task | None = None
        self.afternoon_task: asyncio.Task | None = None
        self.cookie_morning_task: asyncio.Task | None = None
        self.cookie_afternoon_task: asyncio.Task | None = None
        self.is_running = False
        self.collection_manager = None

    def set_collection_manager(self, manager):
        self.collection_manager = manager

    async def start_scheduler(self):
        """Start schedulers: cookie refresh at 5:40 AM / 3:10 PM, collection at 5:45 AM / 3:15 PM."""
        if self.is_running:
            logger.info("Scheduler is already running")
            return

        if not self.collection_manager:
            logger.error("Collection manager not set for scheduler")
            return

        self.is_running = True
        logger.info("Starting collection scheduler...")

        self.morning_task = asyncio.create_task(self._schedule_morning_collection())
        self.afternoon_task = asyncio.create_task(self._schedule_afternoon_collection())
        self.cookie_morning_task = asyncio.create_task(self._schedule_cookie_refresh(time(5, 40, 0), "morning"))
        self.cookie_afternoon_task = asyncio.create_task(self._schedule_cookie_refresh(time(15, 10, 0), "afternoon"))

        logger.info("Schedulers started — cookie refresh at 5:40 AM / 3:10 PM, collection at 5:45 AM / 3:15 PM")

    async def stop_scheduler(self):
        """Stop all scheduled tasks."""
        self.is_running = False

        for task in (self.morning_task, self.afternoon_task,
                     self.cookie_morning_task, self.cookie_afternoon_task):
            if task:
                task.cancel()
        self.morning_task = self.afternoon_task = None
        self.cookie_morning_task = self.cookie_afternoon_task = None

        logger.info("Collection scheduler stopped")

    async def _schedule_morning_collection(self):
        """Schedule collection to start at 5:45 AM daily."""
        while self.is_running:
            now = datetime.now(ZoneInfo("America/Bogota"))
            target_time = time(5, 45, 0)  # 5:45 AM
            
            # Calculate next run time
            next_run = datetime.combine(now.date(), target_time).replace(tzinfo=ZoneInfo("America/Bogota"))
            if now >= next_run:
                next_run = next_run.replace(day=next_run.day + 1)
            
            wait_seconds = (next_run - now).total_seconds()
            logger.info(f"Morning collection scheduled for {next_run} ({wait_seconds:.0f} seconds from now)")
            
            await asyncio.sleep(wait_seconds)
            
            if self.is_running:
                await self._start_collection_if_not_running("morning")

    async def _schedule_afternoon_collection(self):
        """Schedule collection to start at 3:15 PM daily."""
        while self.is_running:
            now = datetime.now(ZoneInfo("America/Bogota"))
            target_time = time(15, 15, 0)  # 3:15 PM
            
            # Calculate next run time
            next_run = datetime.combine(now.date(), target_time).replace(tzinfo=ZoneInfo("America/Bogota"))
            if now >= next_run:
                next_run = next_run.replace(day=next_run.day + 1)
            
            wait_seconds = (next_run - now).total_seconds()
            logger.info(f"Afternoon collection scheduled for {next_run} ({wait_seconds:.0f} seconds from now)")
            
            await asyncio.sleep(wait_seconds)
            
            if self.is_running:
                await self._start_collection_if_not_running("afternoon")

    async def _schedule_cookie_refresh(self, target_time: time, label: str):
        """Run a proactive cookie refresh at the given daily time."""
        while self.is_running:
            now = datetime.now(ZoneInfo("America/Bogota"))
            next_run = datetime.combine(now.date(), target_time).replace(tzinfo=ZoneInfo("America/Bogota"))
            if now >= next_run:
                next_run = next_run.replace(day=next_run.day + 1)
            wait_seconds = (next_run - now).total_seconds()
            logger.info("Cookie refresh (%s) scheduled for %s (%.0fs from now)", label, next_run, wait_seconds)
            await asyncio.sleep(wait_seconds)
            if self.is_running and self.collection_manager is not None:
                try:
                    logger.info("Running proactive cookie refresh (%s)", label)
                    await run_refresh(self.collection_manager)
                except Exception as exc:
                    logger.error("Proactive cookie refresh (%s) failed: %s", label, exc)

    async def _start_collection_if_not_running(self, schedule_type: str):
        """Start collection if it's not already running."""
        try:
            if not self.collection_manager._is_running:
                logger.info(f"Starting {schedule_type} collection as scheduled")
                await self.collection_manager.start()
            else:
                logger.info(f"Skipping {schedule_type} collection - already running")
        except Exception as e:
            logger.error(f"Failed to start {schedule_type} collection: {e}")

# Global scheduler instance
scheduler = Scheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles application startup and shutdown events.
    """
    # Startup
    init_db()
    
    # Initialize Redis message queue
    try:
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        message_queue = MessageQueue(redis_url)
        collection_manager.message_queue = message_queue
        logger.info("Redis message queue initialized successfully")
    except Exception as e:
        logger.warning(f"Failed to initialize Redis message queue: {e}. Running without messaging.")
        message_queue = None
    
    scheduler.set_collection_manager(collection_manager)
    await scheduler.start_scheduler()
    logger.info("FastAPI application startup complete - scheduler running")
    
    yield
    
    # Shutdown
    await scheduler.stop_scheduler()
    if collection_manager._is_running:
        logger.info("Shutting down running collection task")
        await collection_manager.stop()
    logger.info("FastAPI application shutdown complete")

app = FastAPI(lifespan=lifespan)

app.include_router(data_server_router, prefix="/data", tags=["data"])


@app.get("/health")
async def health():
    """Simple health endpoint for load balancers and checks."""
    return {"status": "ok"}

@app.post("/session/set-cookies")
async def set_session_cookies(cookies: dict):
    """
    Receives authenticated session cookies from the cookie-refresher microservice.

    Called automatically by the cookie-refresher agent after it logs in and extracts
    cf_clearance and ci_session. Can also be called manually for testing or recovery.

    Expected payload: {"cf_clearance": "<value>", "ci_session": "<value>"}
    """
    try:
        if not cookies:
            raise ValueError("No cookies provided")

        collection_manager._session_cookies = cookies
        collection_manager._last_login_time = datetime.now(ZoneInfo("America/Bogota"))
        logger.info(f"Session cookies set manually ({len(cookies)} cookies): {list(cookies.keys())}")
        return {
            "message": "Cookies set successfully",
            "session_valid": collection_manager._is_session_valid(),
            "cookies_set": list(cookies.keys()),
            "cookies_count": len(cookies),
            "expires_in_hours": 1.5
        }
    except Exception as e:
        logger.error(f"Failed to set cookies: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/session/status")
async def get_session_status():
    """
    Check current session status and time until expiry.
    Cookies expire after 2 hours - refresh before expiry using /session/set-cookies

    Response:
    {
        "status": "valid" | "expired" | "no_session",
        "message": "...",
        "expires_in_minutes": int,
        "set_at": "ISO timestamp",
        "refresh_instructions": "How to refresh if expired"
    }
    """
    if not collection_manager._last_login_time:
        return {
            "status": "no_session",
            "message": "No session set. Initialize with POST /session/set-cookies",
            "expires_in_seconds": None,
            "expires_in_minutes": None,
            "refresh_instructions": (
                "1. Go to: https://www.rutasljrj.net/rastreo/ljrj/login\n"
                "2. Login with credentials\n"
                "3. Open DevTools (F12) > Application > Cookies\n"
                "4. Copy cf_clearance and ci_session cookies\n"
                "5. POST them to /session/set-cookies endpoint"
            )
        }

    time_since_login = datetime.now(ZoneInfo("America/Bogota")) - collection_manager._last_login_time
    total_lifetime = timedelta(hours=1.5)
    time_remaining = total_lifetime - time_since_login

    is_valid = collection_manager._is_session_valid()

    response = {
        "status": "valid" if is_valid else "expired",
        "message": "✓ Session is valid" if is_valid else "✗ Session expired - refresh needed",
        "set_at": collection_manager._last_login_time.isoformat(),
        "expires_in_seconds": max(0, int(time_remaining.total_seconds())),
        "expires_in_minutes": max(0, int(time_remaining.total_seconds() / 60)),
        "cookies": list(collection_manager._session_cookies.keys()) if collection_manager._session_cookies else []
    }

    if not is_valid:
        response["refresh_instructions"] = (
            "Session EXPIRED. To refresh:\n"
            "1. Go to: https://www.rutasljrj.net/rastreo/ljrj/login\n"
            "2. Login and solve any Cloudflare challenges\n"
            "3. Extract cf_clearance and ci_session cookies\n"
            "4. POST: curl -X POST http://localhost:8000/session/set-cookies -H 'Content-Type: application/json' "
            "-d '{\"cf_clearance\": \"...\", \"ci_session\": \"...\"}'"
        )

    return response


@app.post("/fetch-remote-data")
async def fetch_data_from_remote_service():
    """
    Manual endpoint to fetch data from remote service.
    """
    logger.info("Manual data fetch requested")
    try:
        data = await collection_manager._fetch_remote_data_async()
        return {
            "message": "Data successfully fetched from remote service.",
            "data": data.dict()
        }
    except Exception as e:
        logger.error(f"Error during manual data fetch: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch data: {e}"
        )

@app.post("/collect/start", response_model=CollectionStatusResponse)
async def start_collection():
    """
    Manually start the background data collection task.
    """
    try:
        if collection_manager._is_running:
            raise HTTPException(
                status_code=400,
                detail=f"Collection is already running (Status: {collection_manager._status.value})"
            )

        await collection_manager.start()
        status = await collection_manager.get_status()
        return status

    except HTTPException:
        # Re-raise HTTP exceptions as-is (don't convert to 500)
        raise
    except Exception as e:
        logger.error(f"Error starting collection: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start collection: {e}"
        )

@app.post("/collect/stop", response_model=CollectionStatusResponse)
async def stop_collection():
    """
    Manually stop the background data collection task.
    """
    if not collection_manager._is_running:
        raise HTTPException(
            status_code=400,
            detail="Collection task is not currently running."
        )
    
    await collection_manager.stop()
    status = await collection_manager.get_status()
    return status

@app.get("/collect/status", response_model=CollectionStatusResponse)
async def get_collection_status():
    """
    Returns the current status and metadata of the collection task.
    """
    status = await collection_manager.get_status()
    # Add scheduler info to the status
    status_dict = status.dict()
    status_dict["scheduler_running"] = scheduler.is_running
    status_dict["scheduled_times"] = "6:00 AM and 3:15 PM daily"
    return CollectionStatusResponse(**status_dict)

@app.post("/scheduler/start")
async def start_scheduler():
    """
    Manually start the collection scheduler.
    """
    await scheduler.start_scheduler()
    return {"message": "Collection scheduler started"}

@app.post("/scheduler/stop")
async def stop_scheduler():
    """
    Manually stop the collection scheduler.
    """
    await scheduler.stop_scheduler()
    return {"message": "Collection scheduler stopped"}

@app.get("/scheduler/status")
async def get_scheduler_status():
    """
    Get the current status of the scheduler.
    """
    return {
        "scheduler_running": scheduler.is_running,
        "collection_running": collection_manager._is_running,
        "next_morning_run": "6:00 AM daily",
        "next_afternoon_run": "3:15 PM daily",
        "timezone": "America/Bogota"
    }

@app.post("/session/refresh")
async def trigger_cookie_refresh():
    """
    Manually trigger the programmed cookie refresh flow.

    Starts the VNC browser container, runs the pre-recorded login steps,
    and stores the resulting cookies in-process. Useful for recovery when
    the session has expired outside the scheduled refresh windows.
    """
    try:
        success = await run_refresh(collection_manager)
        if success:
            return {"success": True, "message": "Cookie refresh completed successfully"}
        raise HTTPException(status_code=500, detail="Cookie refresh failed — check logs for details")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Unexpected error during manual cookie refresh: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))