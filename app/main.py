from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from app.database import init_db, get_db
from app.models import TimestampEntry
from typing import List

# Initialize the FastAPI application
app = FastAPI(
    title="FastAPI Web Scraper Scheduler API",
    description="API for managing and serving web scraped data updates.",
    version="1.0.0"
)

# --- Startup Event Handler ---
@app.on_event("startup")
def on_startup():
    """
    Initializes the database tables on application startup.
    """
    print("Initializing database tables...")
    init_db()
    print("Database initialization complete.")

# --- API Endpoints ---

# 1. Endpoint to store the current time in the database
@app.post("/record-time", response_model=dict, status_code=201)
def record_current_timestamp(db: Session = Depends(get_db)):
    """
    Records the current UTC timestamp in the database.
    """
    try:
        # Create a new model instance
        new_entry = TimestampEntry(timestamp=datetime.utcnow())
        
        # Add to the session and commit the transaction
        db.add(new_entry)
        db.commit()
        
        # Refresh the instance to get the generated ID and actual timestamp from the DB
        db.refresh(new_entry)
        
        # Return a confirmation response
        return {
            "message": "Timestamp recorded successfully",
            "id": new_entry.id,
            "timestamp_utc": new_entry.timestamp.isoformat()
        }
    except Exception as e:
        db.rollback()
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Could not record timestamp due to a server error.")

# 2. Endpoint to retrieve all recorded times (for verification)
@app.get("/recorded-times", response_model=List[dict])
def get_recorded_timestamps(db: Session = Depends(get_db)):
    """
    Retrieves all recorded timestamps from the database.
    """
    # Query all entries and order by ID descending (most recent first)
    entries = db.query(TimestampEntry).order_by(TimestampEntry.id.desc()).all()
    
    # Format the output
    results = [
        {"id": entry.id, "timestamp_utc": entry.timestamp.isoformat()}
        for entry in entries
    ]
    return results

# 3. Simple root health check
@app.get("/", response_model=dict)
async def root():
    return {"status": "ok", "service": "fastapi_api"}