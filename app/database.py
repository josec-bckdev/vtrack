from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base
import os
from dotenv import load_dotenv

# Load environment variables (important for local testing outside Docker)
load_dotenv()

# The database URL is typically pulled from environment variables.
# In a docker-compose setup, this will be provided by the 'environment' block.
# We use a default for non-docker execution or testing.
SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://user:password@localhost:5432/timestamps_db"
)

# 1. Create the SQLAlchemy Engine
# The pool_pre_ping=True helps reconnect if the DB connection is dropped.
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    pool_pre_ping=True,
    # Setting echo=True prints all SQL queries (useful for debugging)
    # echo=True 
)

# 2. Configure the Session
# This session will be used to interact with the database.
# autocommit=False: allows us to commit transactions explicitly.
# autoflush=False: prevents the session from sending SQL to the DB automatically before a query.
# bind=engine: associates this SessionLocal with our engine.
SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine
)

def init_db():
    """
    Creates the database tables defined in models.py (if they don't exist).
    This function should be called when the application starts.
    """
    Base.metadata.create_all(bind=engine)

# Dependency to get a database session for FastAPI endpoints
def get_db():
    """
    Generator function to yield a database session (for FastAPI dependency injection).
    Handles closing the session automatically.
    """
    db = SessionLocal()
    try:
        # Provide the session object to the caller
        yield db
    finally:
        # Ensure the session is closed after the request is processed
        db.close()