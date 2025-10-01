import pytest
import httpx
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import get_db, Base
from app.models import TimestampEntry

# --- Setup for Testing ---

# 1. Use an in-memory SQLite database for fast, isolated testing
# Note: For production-critical apps, you might use a dedicated test Postgres DB.
# SQLite is used here for simplicity and speed.
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 2. Override the dependency to use the test database session
def override_get_db():
    """
    Provides a clean, independent session for each test.
    """
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

# Apply the override to the main app instance
app.dependency_overrides[get_db] = override_get_db

# 3. Setup and Teardown for tests
@pytest.fixture(scope="session", autouse=True)
def setup_db():
    """
    Creates and drops tables once per testing session.
    """
    # Create all tables (runs before tests)
    Base.metadata.create_all(bind=engine)
    yield
    # Drop all tables (runs after all tests)
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def test_client():
    """
    A fixture to provide a test client for API calls.
    Cleans the database before each test.
    """
    # Clean up the table before each test run
    db = TestingSessionLocal()
    db.query(TimestampEntry).delete()
    db.commit()
    db.close()
    
    # Use httpx.Client for synchronous testing of the FastAPI app
    with httpx.Client(app=app, base_url="http://test") as client:
        yield client

# --- Test Cases ---

def test_record_time_success(test_client):
    """
    Test that the POST /record-time endpoint successfully stores a timestamp.
    """
    response = test_client.post("/record-time")
    
    # 1. Check response status code
    assert response.status_code == 201
    
    data = response.json()
    
    # 2. Check response structure and content
    assert "message" in data
    assert data["message"] == "Timestamp recorded successfully"
    assert "id" in data
    assert "timestamp_utc" in data
    
    # 3. Verify the data was actually saved to the database
    db = TestingSessionLocal()
    saved_entry = db.get(TimestampEntry, data["id"])
    db.close()

    assert saved_entry is not None
    assert saved_entry.id == data["id"]
    
    # Check if the saved timestamp is close to current time (within 5 seconds)
    saved_time = datetime.fromisoformat(data["timestamp_utc"])
    time_difference = datetime.utcnow() - saved_time
    assert abs(time_difference.total_seconds()) < 5

def test_get_recorded_times_empty(test_client):
    """
    Test that the GET /recorded-times endpoint returns an empty list when no data exists.
    """
    response = test_client.get("/recorded-times")
    assert response.status_code == 200
    assert response.json() == []

def test_get_recorded_times_multiple_entries(test_client):
    """
    Test that the GET /recorded-times endpoint returns all recorded entries.
    """
    # Record two times
    test_client.post("/record-time")
    test_client.post("/record-time")

    response = test_client.get("/recorded-times")
    
    # Check status and count
    assert response.status_code == 200
    entries = response.json()
    assert len(entries) == 2
    
    # Check order (most recent first, so ID 2 should be first)
    assert entries[0]["id"] > entries[1]["id"]
    
    # Check structure
    assert "id" in entries[0]
    assert "timestamp_utc" in entries[0]