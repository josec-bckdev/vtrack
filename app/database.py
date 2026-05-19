import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base

# Determine the database URL based on environment (using sqlite for testing)
SQLALCHEMY_DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://user:password@db:5432/app_db")
TESTING = os.environ.get("TESTING") == "1"

if TESTING:
    # Use an in-memory SQLite database for testing
    SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    # Use PostgreSQL engine
    engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Special session for testing to ensure isolation
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Initializes the database by creating all defined tables."""
    print("Initializing database...")
    if TESTING and os.path.exists("./test.db"):
        # Delete previous test DB to ensure a clean slate
        os.remove("./test.db")
    
    # Create tables defined in Base (from app.models)
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully.")

def get_db():
    """Dependency to provide a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_session():
    """Session factory for non-FastAPI consumers (e.g. SqlAlchemyRouteRepository)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Initialize the database immediately when the module is imported
# The lifespan event in main.py will call init_db() on startup.