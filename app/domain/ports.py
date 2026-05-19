from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from app.models import CollectionStatusEnum


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
