"""
Tests for IRouteDataRepository port and SqlAlchemyRouteRepository adapter.

Organised in two sections:
  1. Port contract — verifies IRouteDataRepository is an importable ABC
     with the correct abstract method signatures.
  2. Adapter integration — verifies SqlAlchemyRouteRepository persists data
     correctly using the in-memory SQLite session from conftest.
"""

import pytest
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import MagicMock

from app.models import CollectionStatusEnum


# =============================================================================
# PORT CONTRACT TESTS  (RED until app/domain/ports.py exists)
# =============================================================================

class TestIRouteDataRepositoryContract:
    """IRouteDataRepository must be abstract and declare the correct interface."""

    def test_port_is_importable(self):
        from app.domain.ports import IRouteDataRepository
        assert IRouteDataRepository is not None

    def test_port_cannot_be_instantiated_directly(self):
        from app.domain.ports import IRouteDataRepository
        with pytest.raises(TypeError):
            IRouteDataRepository()

    def test_concrete_subclass_must_implement_all_methods(self):
        from app.domain.ports import IRouteDataRepository

        class Incomplete(IRouteDataRepository):
            pass  # implements nothing

        with pytest.raises(TypeError):
            Incomplete()

    def test_complete_subclass_is_instantiable(self):
        from app.domain.ports import IRouteDataRepository

        class Stub(IRouteDataRepository):
            def create_task(self, start_time): return 1
            def update_task_status(self, task_id, status, update_time, stop_time=None): pass
            def save_route_entry(self, normalized_data): pass
            def update_task_datapoints(self, task_id, count): pass

        repo = Stub()
        assert isinstance(repo, IRouteDataRepository)

    def test_create_task_signature(self):
        """create_task(start_time) -> int"""
        import inspect
        from app.domain.ports import IRouteDataRepository
        sig = inspect.signature(IRouteDataRepository.create_task)
        assert "start_time" in sig.parameters

    def test_update_task_status_signature(self):
        """update_task_status(task_id, status, update_time, stop_time=None)"""
        import inspect
        from app.domain.ports import IRouteDataRepository
        sig = inspect.signature(IRouteDataRepository.update_task_status)
        params = sig.parameters
        assert "task_id" in params
        assert "status" in params
        assert "update_time" in params
        assert "stop_time" in params
        assert params["stop_time"].default is None

    def test_save_route_entry_signature(self):
        """save_route_entry(normalized_data)"""
        import inspect
        from app.domain.ports import IRouteDataRepository
        sig = inspect.signature(IRouteDataRepository.save_route_entry)
        assert "normalized_data" in sig.parameters

    def test_update_task_datapoints_signature(self):
        """update_task_datapoints(task_id, count)"""
        import inspect
        from app.domain.ports import IRouteDataRepository
        sig = inspect.signature(IRouteDataRepository.update_task_datapoints)
        params = sig.parameters
        assert "task_id" in params
        assert "count" in params


# =============================================================================
# ADAPTER INTEGRATION TESTS  (RED until app/adapters/route_repository.py exists)
# =============================================================================

@pytest.fixture
def repo(db_session):
    """SqlAlchemyRouteRepository wired to the in-memory test session."""
    from app.adapters.route_repository import SqlAlchemyRouteRepository
    return SqlAlchemyRouteRepository(get_session=lambda: db_session)


class TestSqlAlchemyRouteRepositoryCreateTask:

    def test_returns_integer_id(self, repo):
        now = datetime.now(ZoneInfo("America/Bogota"))
        task_id = repo.create_task(now)
        assert isinstance(task_id, int)
        assert task_id > 0

    def test_persists_metadata_row(self, repo, db_session):
        from app.models import CollectionMetadata
        now = datetime.now(ZoneInfo("America/Bogota"))
        repo.create_task(now)
        row = db_session.query(CollectionMetadata).first()
        assert row is not None
        assert row.status == CollectionStatusEnum.IDLE.value

    def test_start_time_is_stored(self, repo, db_session):
        from app.models import CollectionMetadata
        now = datetime(2025, 6, 1, 7, 0, 0, tzinfo=ZoneInfo("America/Bogota"))
        repo.create_task(now)
        row = db_session.query(CollectionMetadata).first()
        assert row.start_time == now


class TestSqlAlchemyRouteRepositoryUpdateTaskStatus:

    def test_status_is_updated(self, repo, db_session):
        from app.models import CollectionMetadata
        now = datetime.now(ZoneInfo("America/Bogota"))
        task_id = repo.create_task(now)

        repo.update_task_status(task_id, CollectionStatusEnum.ONGOING, now)

        db_session.expire_all()
        row = db_session.query(CollectionMetadata).get(task_id)
        assert row.status == CollectionStatusEnum.ONGOING.value

    def test_stop_time_set_when_provided(self, repo, db_session):
        from app.models import CollectionMetadata
        start = datetime(2025, 6, 1, 7, 0, 0, tzinfo=ZoneInfo("America/Bogota"))
        stop  = datetime(2025, 6, 1, 8, 0, 0, tzinfo=ZoneInfo("America/Bogota"))
        task_id = repo.create_task(start)

        repo.update_task_status(task_id, CollectionStatusEnum.FINISHED, stop, stop_time=stop)

        db_session.expire_all()
        row = db_session.query(CollectionMetadata).get(task_id)
        assert row.stop_time == stop

    def test_stop_time_not_set_when_none(self, repo, db_session):
        from app.models import CollectionMetadata
        now = datetime.now(ZoneInfo("America/Bogota"))
        task_id = repo.create_task(now)

        repo.update_task_status(task_id, CollectionStatusEnum.ONGOING, now)

        db_session.expire_all()
        row = db_session.query(CollectionMetadata).get(task_id)
        assert row.stop_time is None


class TestSqlAlchemyRouteRepositorySaveRouteEntry:

    def test_row_is_inserted(self, repo, db_session, sample_route_data):
        from app.models import RouteDataEntry
        repo.save_route_entry(sample_route_data)
        row = db_session.query(RouteDataEntry).first()
        assert row is not None
        assert row.ruta == sample_route_data["ruta"]

    def test_coordinates_are_stored(self, repo, db_session, sample_route_data):
        from app.models import RouteDataEntry
        repo.save_route_entry(sample_route_data)
        row = db_session.query(RouteDataEntry).first()
        assert row.ns_latitude == sample_route_data["ns_latitude"]
        assert row.ew_longitude == sample_route_data["ew_longitude"]


class TestSqlAlchemyRouteRepositoryUpdateTaskDatapoints:

    def test_datapoints_count_updated(self, repo, db_session):
        from app.models import CollectionMetadata
        now = datetime.now(ZoneInfo("America/Bogota"))
        task_id = repo.create_task(now)

        repo.update_task_datapoints(task_id, 5)

        db_session.expire_all()
        row = db_session.query(CollectionMetadata).get(task_id)
        assert row.datapoints_count == 5

    def test_unknown_task_id_is_silently_ignored(self, repo):
        # should not raise
        repo.update_task_datapoints(99999, 10)
