import logging
from datetime import datetime
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from app.domain.ports import IRouteDataRepository
from app.models import CollectionMetadata, CollectionStatusEnum, RouteDataEntry

logger = logging.getLogger(__name__)


class SqlAlchemyRouteRepository(IRouteDataRepository):
    """Persists route collection data via SQLAlchemy.

    get_session: zero-arg callable returning an open Session.
    Defaults to the app-wide get_db_session generator from scraper_async.
    """

    def __init__(self, get_session: Optional[Callable] = None):
        if get_session is None:
            from app.database import get_db_session
            get_session = lambda: next(get_db_session())  # noqa: E731
        self._get_session = get_session

    def create_task(self, start_time: datetime) -> int:
        db = self._get_session()
        try:
            entry = CollectionMetadata(
                start_time=start_time,
                status=CollectionStatusEnum.IDLE.value,
                last_update_time=start_time,
            )
            db.add(entry)
            db.commit()
            return entry.id
        finally:
            db.close()

    def update_task_status(
        self,
        task_id: int,
        status: CollectionStatusEnum,
        update_time: datetime,
        stop_time: Optional[datetime] = None,
    ) -> None:
        db = self._get_session()
        try:
            metadata = db.query(CollectionMetadata).get(task_id)
            if metadata:
                metadata.status = status.value
                metadata.last_update_time = update_time
                if stop_time is not None:
                    metadata.stop_time = stop_time
                db.commit()
        finally:
            db.close()

    def save_route_entry(self, normalized_data: dict) -> None:
        db = self._get_session()
        try:
            entry = RouteDataEntry(**normalized_data)
            db.add(entry)
            db.commit()
            logger.info(f"Saved route data for ruta {normalized_data['ruta']}")
        except Exception as e:
            logger.error(f"Error saving route data: {e}")
            db.rollback()
            raise
        finally:
            db.close()

    def update_task_datapoints(self, task_id: int, count: int) -> None:
        db = self._get_session()
        try:
            metadata = db.query(CollectionMetadata).get(task_id)
            if metadata:
                metadata.datapoints_count = count
                db.commit()
        finally:
            db.close()
