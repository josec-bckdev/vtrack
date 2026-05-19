from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.models import CollectionStatusEnum


@dataclass
class CollectionSnapshot:
    task_id: Optional[int] = None
    status: CollectionStatusEnum = field(default_factory=lambda: CollectionStatusEnum.IDLE)
    start_time: Optional[datetime] = None
    stop_time: Optional[datetime] = None
    datapoints_collected: int = 0


class ICollectionStateStore(ABC):

    @abstractmethod
    def initialize(self, task_id: int, start_time: datetime) -> None:
        """Reset all state for a new collection run."""

    @abstractmethod
    def set_status(self, status: CollectionStatusEnum, stop_time: Optional[datetime] = None) -> None:
        """Update status; if stop_time is provided, record it."""

    @abstractmethod
    def increment_datapoints(self) -> int:
        """Increment the datapoints counter and return the new value."""

    @abstractmethod
    def check_and_update_hash(self, data_hash: str) -> bool:
        """Return True if hash differs from last seen; update stored hash."""

    @abstractmethod
    def get_snapshot(self) -> CollectionSnapshot:
        """Return a point-in-time snapshot of the current state."""


class ICollectionStatusAdapter(ABC):

    @abstractmethod
    def is_running(self) -> bool:
        """Return True if a collection is currently active."""

    @abstractmethod
    async def start(self) -> None:
        """Start a new collection run."""


class IRouteDataRepository(ABC):

    @abstractmethod
    def create_task(self, start_time: datetime) -> int:
        """Insert a CollectionMetadata row and return its generated id."""

    @abstractmethod
    def update_task_status(
        self,
        task_id: int,
        status: CollectionStatusEnum,
        update_time: datetime,
        stop_time: Optional[datetime] = None,
    ) -> None:
        """Update status, last_update_time, and optionally stop_time."""

    @abstractmethod
    def save_route_entry(self, normalized_data: dict) -> None:
        """Insert a RouteDataEntry row."""

    @abstractmethod
    def update_task_datapoints(self, task_id: int, count: int) -> None:
        """Set datapoints_count on the CollectionMetadata row."""
