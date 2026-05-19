"""
Tests for ICollectionStateStore port and InMemoryCollectionState adapter.

Section 1: Port contract — ICollectionStateStore is an importable ABC
            with the correct abstract method signatures, and CollectionSnapshot
            is a dataclass with the right fields.

Section 2: Adapter behaviour — InMemoryCollectionState correctly tracks state
            through the full lifecycle of a collection run.
"""

import pytest
from datetime import datetime
from zoneinfo import ZoneInfo

from app.models import CollectionStatusEnum


# =============================================================================
# PORT CONTRACT TESTS  (RED until app/domain/ports.py is updated)
# =============================================================================

class TestCollectionSnapshotContract:

    def test_snapshot_is_importable(self):
        from app.domain.ports import CollectionSnapshot
        assert CollectionSnapshot is not None

    def test_snapshot_has_required_fields(self):
        from app.domain.ports import CollectionSnapshot
        snap = CollectionSnapshot()
        assert hasattr(snap, "task_id")
        assert hasattr(snap, "status")
        assert hasattr(snap, "start_time")
        assert hasattr(snap, "stop_time")
        assert hasattr(snap, "datapoints_collected")

    def test_snapshot_defaults(self):
        from app.domain.ports import CollectionSnapshot
        snap = CollectionSnapshot()
        assert snap.task_id is None
        assert snap.status == CollectionStatusEnum.IDLE
        assert snap.start_time is None
        assert snap.stop_time is None
        assert snap.datapoints_collected == 0


class TestICollectionStateStoreContract:

    def test_port_is_importable(self):
        from app.domain.ports import ICollectionStateStore
        assert ICollectionStateStore is not None

    def test_port_cannot_be_instantiated_directly(self):
        from app.domain.ports import ICollectionStateStore
        with pytest.raises(TypeError):
            ICollectionStateStore()

    def test_complete_subclass_is_instantiable(self):
        from app.domain.ports import ICollectionStateStore, CollectionSnapshot
        from datetime import datetime

        class Stub(ICollectionStateStore):
            def initialize(self, task_id, start_time): pass
            def set_status(self, status, stop_time=None): pass
            def increment_datapoints(self): return 1
            def check_and_update_hash(self, data_hash): return True
            def get_snapshot(self): return CollectionSnapshot()

        assert isinstance(Stub(), ICollectionStateStore)

    def test_initialize_signature(self):
        import inspect
        from app.domain.ports import ICollectionStateStore
        sig = inspect.signature(ICollectionStateStore.initialize)
        assert "task_id" in sig.parameters
        assert "start_time" in sig.parameters

    def test_set_status_has_optional_stop_time(self):
        import inspect
        from app.domain.ports import ICollectionStateStore
        sig = inspect.signature(ICollectionStateStore.set_status)
        assert "status" in sig.parameters
        assert "stop_time" in sig.parameters
        assert sig.parameters["stop_time"].default is None

    def test_increment_datapoints_signature(self):
        import inspect
        from app.domain.ports import ICollectionStateStore
        sig = inspect.signature(ICollectionStateStore.increment_datapoints)
        assert len([p for p in sig.parameters if p != "self"]) == 0

    def test_check_and_update_hash_signature(self):
        import inspect
        from app.domain.ports import ICollectionStateStore
        sig = inspect.signature(ICollectionStateStore.check_and_update_hash)
        assert "data_hash" in sig.parameters

    def test_get_snapshot_signature(self):
        import inspect
        from app.domain.ports import ICollectionStateStore
        sig = inspect.signature(ICollectionStateStore.get_snapshot)
        assert len([p for p in sig.parameters if p != "self"]) == 0


# =============================================================================
# ADAPTER TESTS  (RED until app/adapters/collection_state.py exists)
# =============================================================================

@pytest.fixture
def state():
    from app.adapters.collection_state import InMemoryCollectionState
    return InMemoryCollectionState()


NOW = datetime(2025, 6, 1, 7, 0, 0, tzinfo=ZoneInfo("America/Bogota"))
LATER = datetime(2025, 6, 1, 8, 0, 0, tzinfo=ZoneInfo("America/Bogota"))


class TestInMemoryCollectionStateInitialize:

    def test_fresh_instance_returns_idle_snapshot(self, state):
        snap = state.get_snapshot()
        assert snap.status == CollectionStatusEnum.IDLE
        assert snap.task_id is None
        assert snap.datapoints_collected == 0

    def test_initialize_sets_task_id_and_start_time(self, state):
        state.initialize(task_id=42, start_time=NOW)
        snap = state.get_snapshot()
        assert snap.task_id == 42
        assert snap.start_time == NOW

    def test_initialize_resets_datapoints_to_zero(self, state):
        state.initialize(42, NOW)
        state.increment_datapoints()
        state.increment_datapoints()
        state.initialize(99, LATER)  # second run
        assert state.get_snapshot().datapoints_collected == 0

    def test_initialize_clears_stop_time(self, state):
        state.initialize(1, NOW)
        state.set_status(CollectionStatusEnum.FINISHED, stop_time=LATER)
        state.initialize(2, LATER)  # new run
        assert state.get_snapshot().stop_time is None


class TestInMemoryCollectionStateSetStatus:

    def test_set_status_updates_status(self, state):
        state.initialize(1, NOW)
        state.set_status(CollectionStatusEnum.ONGOING)
        assert state.get_snapshot().status == CollectionStatusEnum.ONGOING

    def test_set_status_sets_stop_time_when_provided(self, state):
        state.initialize(1, NOW)
        state.set_status(CollectionStatusEnum.FINISHED, stop_time=LATER)
        assert state.get_snapshot().stop_time == LATER

    def test_set_status_does_not_clear_stop_time_when_none(self, state):
        state.initialize(1, NOW)
        state.set_status(CollectionStatusEnum.FINISHED, stop_time=LATER)
        state.set_status(CollectionStatusEnum.IDLE)  # no stop_time passed
        assert state.get_snapshot().stop_time == LATER  # previous stop_time preserved


class TestInMemoryCollectionStateIncrementDatapoints:

    def test_increment_returns_new_count(self, state):
        state.initialize(1, NOW)
        assert state.increment_datapoints() == 1
        assert state.increment_datapoints() == 2
        assert state.increment_datapoints() == 3

    def test_snapshot_reflects_incremented_count(self, state):
        state.initialize(1, NOW)
        state.increment_datapoints()
        state.increment_datapoints()
        assert state.get_snapshot().datapoints_collected == 2


class TestInMemoryCollectionStateCheckAndUpdateHash:

    def test_first_call_always_returns_true(self, state):
        assert state.check_and_update_hash("hash-abc") is True

    def test_same_hash_returns_false(self, state):
        state.check_and_update_hash("hash-abc")
        assert state.check_and_update_hash("hash-abc") is False

    def test_different_hash_returns_true(self, state):
        state.check_and_update_hash("hash-abc")
        assert state.check_and_update_hash("hash-xyz") is True

    def test_hash_resets_on_initialize(self, state):
        state.initialize(1, NOW)
        state.check_and_update_hash("hash-abc")
        state.initialize(2, LATER)
        assert state.check_and_update_hash("hash-abc") is True  # hash was cleared
