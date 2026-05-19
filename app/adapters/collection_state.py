from datetime import datetime
from typing import Optional

from app.domain.ports import CollectionSnapshot, ICollectionStateStore
from app.models import CollectionStatusEnum


class InMemoryCollectionState(ICollectionStateStore):

    def __init__(self):
        self._snapshot = CollectionSnapshot()
        self._last_hash: Optional[str] = None

    def initialize(self, task_id: int, start_time: datetime) -> None:
        self._snapshot = CollectionSnapshot(
            task_id=task_id,
            status=CollectionStatusEnum.IDLE,
            start_time=start_time,
            stop_time=None,
            datapoints_collected=0,
        )
        self._last_hash = None

    def set_status(self, status: CollectionStatusEnum, stop_time: Optional[datetime] = None) -> None:
        self._snapshot.status = status
        if stop_time is not None:
            self._snapshot.stop_time = stop_time

    def increment_datapoints(self) -> int:
        self._snapshot.datapoints_collected += 1
        return self._snapshot.datapoints_collected

    def check_and_update_hash(self, data_hash: str) -> bool:
        if data_hash == self._last_hash:
            return False
        self._last_hash = data_hash
        return True

    def get_snapshot(self) -> CollectionSnapshot:
        return self._snapshot
