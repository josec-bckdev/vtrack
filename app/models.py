from sqlalchemy import Column, Integer, DateTime
from sqlalchemy.orm import declarative_base
from datetime import datetime

# Base class from which all model classes inherit
Base = declarative_base()

class TimestampEntry(Base):
    """
    SQLAlchemy model for storing timestamp entries.
    """
    __tablename__ = 'timestamp_entries'
    
    # Primary key: automatically increments
    id = Column(Integer, primary_key=True, index=True)
    
    # The timestamp of when the entry was recorded
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<TimestampEntry(id={self.id}, timestamp='{self.timestamp}')>"
