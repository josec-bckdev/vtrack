import logging
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, time
from zoneinfo import ZoneInfo
from fastapi import FastAPI, HTTPException
from app.database import init_db
from .data_server import router as data_server_router
from app.scraper_async import collection_manager
from app.models import CollectionStatusResponse, CollectionStatusEnum
from shared.message_queue import MessageQueue
import os

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Scheduler:
    """Manages scheduled collection tasks."""
    
    def __init__(self):
        self.morning_task: asyncio.Task | None = None
        self.afternoon_task: asyncio.Task | None = None
        self.is_running = False
        self.collection_manager = None

    def set_collection_manager(self, manager):
        """Set the collection manager instance."""
        self.collection_manager = manager

    async def start_scheduler(self):
        """Start the scheduler to run collection at 5:45 AM and 3:15 PM daily."""
        if self.is_running:
            logger.info("Scheduler is already running")
            return
            
        if not self.collection_manager:
            logger.error("Collection manager not set for scheduler")
            return
            
        self.is_running = True
        logger.info("Starting collection scheduler...")
        
        # Start both scheduled tasks
        self.morning_task = asyncio.create_task(self._schedule_morning_collection())
        self.afternoon_task = asyncio.create_task(self._schedule_afternoon_collection())
        
        logger.info("Collection scheduler started - will run at 5:45 AM and 3:15 PM daily")

    async def stop_scheduler(self):
        """Stop all scheduled tasks."""
        self.is_running = False
        
        if self.morning_task:
            self.morning_task.cancel()
            self.morning_task = None
            
        if self.afternoon_task:
            self.afternoon_task.cancel()
            self.afternoon_task = None
            
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