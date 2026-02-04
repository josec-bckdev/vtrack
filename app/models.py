from datetime import datetime
from zoneinfo import ZoneInfo
from enum import Enum

from pydantic import BaseModel, Field
from typing import List
from sqlalchemy import Column, Integer, String, DateTime, Float
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class RouteDataEntry(Base):
    """Normalized route data combining position and status information."""
    __tablename__ = "route_data"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Route identification
    ruta = Column(Integer, index=True, nullable=False)
    
    # Position data (from valores)
    ns_latitude = Column(Float, nullable=False)
    ew_longitude = Column(Float, nullable=False)
    position_ts = Column(DateTime, nullable=True)
    
    # Route status (from estados)
    route_status = Column(String, nullable=False)
    route_status_ts = Column(DateTime, nullable=True)
    
    # Student status (from estados)
    student_status = Column(String, nullable=False)
    student_status_ts = Column(DateTime, nullable=True)
    
    # Collection timestamp
    collected_at = Column(
        DateTime,
        default=lambda: datetime.now(ZoneInfo("America/Bogota")),
        nullable=False
    )

class CollectionMetadata(Base):
    """Tracks data collection sessions and their status."""
    __tablename__ = "collection_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    start_time = Column(DateTime, nullable=False)
    stop_time = Column(DateTime, nullable=True)
    status = Column(String, nullable=False)  # IDLE, ONGOING, FINISHED
    datapoints_count = Column(Integer, default=0)
    last_update_time = Column(DateTime, nullable=False)

# Pydantic schemas for API responses
class RouteDataResponse(BaseModel):
    id: int
    ruta: int
    ns_latitude: float
    ew_longitude: float
    position_ts: datetime
    route_status: str
    route_status_ts: datetime
    student_status: str
    student_status_ts: datetime
    collected_at: datetime

    class Config:
        from_attributes = True

class ScrapingResponse(BaseModel):
    source: str
    valores_data: list[list]
    estados_data: list[list]

class CollectionStatusEnum(str, Enum):
    IDLE = "IDLE"
    ONGOING = "ONGOING"
    FINISHED = "FINISHED"

class CollectionStatusResponse(BaseModel):
    task_id: int | None = None
    status: CollectionStatusEnum
    message: str
    start_time: datetime | None = None
    stop_time: datetime | None = None
    datapoints_collected: int = 0
    # Optional scheduler info (added in main.py)
    scheduler_running: bool | None = None
    scheduled_times: str | None = None

    class Config:
        from_attributes = True

# Data Server specific response models

class CollectionMetadataResponse(BaseModel):
    id: int
    start_time: datetime
    stop_time: datetime | None
    status: str
    datapoints_count: int
    last_update_time: datetime

    class Config:
        from_attributes = True

class CollectionWithDataResponse(BaseModel):
    collection: CollectionMetadataResponse
    datapoints: List[RouteDataResponse]

    class Config:
        from_attributes = True

class TimeRangeRequest(BaseModel):
    start: datetime
    stop: datetime
