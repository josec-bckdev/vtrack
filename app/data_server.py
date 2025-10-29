from typing import List

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import models
from .database import get_db

router = APIRouter()

# Reusable helper to query datapoints between two datetimes
def get_datapoints_by_time_range(
        db: Session, 
        start: datetime, 
        stop: datetime
        ) -> List[models.RouteDataEntry]:
    if start > stop:
        raise HTTPException(status_code=400, detail="start must be <= stop")
    return (
        db.query(models.RouteDataEntry)
        .filter(models.RouteDataEntry.collected_at >= start)
        .filter(models.RouteDataEntry.collected_at <= stop)
        .all()
    )

@router.get("/sessions/{session_id}/datapoints", response_model=models.CollectionWithDataResponse)
def get_session_datapoints(session_id: int, db: Session = Depends(get_db)):
    """
    Return a collection session (by id) and all RouteDataEntry rows whose
    collected_at is between the session's start_time and stop_time.

    If stop_time is null, it will use the current time in America/Bogota.
    """
    session = db.query(models.CollectionMetadata).filter(
        models.CollectionMetadata.id == session_id
        ).first()
    if not session:
        raise HTTPException(status_code=404, detail="CollectionMetadata not found")

    start = session.start_time
    stop = session.stop_time or datetime.now(ZoneInfo("America/Bogota"))

    datapoints = get_datapoints_by_time_range(db, start, stop)

    return {"collection": session, "datapoints": datapoints}

@router.post("/datapoints/range", response_model=List[models.RouteDataResponse])
def datapoints_by_range(payload: models.TimeRangeRequest, db: Session = Depends(get_db)):
    """
    Return RouteDataEntry rows whose collected_at is between the provided start and stop timestamps.
    Expects JSON body: { "start": "<ISO datetime>", "stop": "<ISO datetime>" }
    """
    return get_datapoints_by_time_range(db, payload.start, payload.stop)