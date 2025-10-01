import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from requests.exceptions import RequestException

from app.database import get_db, init_db
from app.scraper_async import collection_manager
from app.models import CollectionStatusResponse, CollectionStatusEnum

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles application startup and shutdown events."""
    init_db()
    logger.info("FastAPI application startup complete.")
    yield
    if collection_manager._is_running:
        logger.info("Shutting down background collection task.")
        await collection_manager.stop()
    logger.info("FastAPI application shutdown complete.")

app = FastAPI(lifespan=lifespan)

@app.post("/fetch-remote-data")
async def fetch_data_from_remote_service():
    """Performs the multi-step login and data fetching in a synchronous call."""
    logger.info("Received request to fetch data from remote service.")
    try:
        data = await collection_manager._fetch_remote_data_async()
        return {
            "message": "Data successfully fetched from remote service.",
            "data": data.dict()
        }
    except RequestException as e:
        logger.error(f"HTTP/Network Error during remote data fetching: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Service Unavailable: Could not connect to remote service or login failed. Details: {e}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during remote data fetching: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal Server Error: {e}"
        )

@app.post("/collect/start", response_model=CollectionStatusResponse)
async def start_collection(background_tasks: BackgroundTasks):
    """Starts the background data collection task."""
    try:
        if collection_manager._is_running:
            raise HTTPException(
                status_code=400,
                detail=f"Collection is already running (Status: {collection_manager._status.value}). Stop it first or check status."
            )
        
        await collection_manager.start()
        status = await collection_manager.get_status()
        return status

    except Exception as e:
        logger.error(f"Error starting collection: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start collection: {e}"
        )

@app.post("/collect/stop", response_model=CollectionStatusResponse)
async def stop_collection():
    """Stops the background data collection task."""
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
    """Returns the current status and metadata of the collection task."""
    status = await collection_manager.get_status()
    return status