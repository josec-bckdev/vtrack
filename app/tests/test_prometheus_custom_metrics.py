"""RED tests — custom Prometheus metrics.

Verify that:
  - vtrack_collection_total{slot, outcome}     increments in _run_and_record
  - vtrack_guardian_state{slot, state}         updates on every state transition in _watch_slot
  - vtrack_collection_datapoints{slot}         observes datapoints in AsyncCollectionManager.stop()

Fails until app/metrics.py is created and the scheduler/scraper are instrumented.
"""
import asyncio
import pytest
from datetime import datetime, time
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

from prometheus_client import REGISTRY

from app.config import JobSlot
from app.scheduler import Scheduler, GuardianState
from app.scraper_async import AsyncCollectionManager


TZ = ZoneInfo("America/Bogota")

# Unique slot prefixes per class keep counters isolated across test runs
# (Prometheus counters accumulate within a process — unique labels avoid overlap)


def _sample(metric_name: str, **labels) -> float | None:
    """Return the first matching sample value from the default registry."""
    for metric in REGISTRY.collect():
        for s in metric.samples:
            if s.name == metric_name and all(
                s.labels.get(k) == v for k, v in labels.items()
            ):
                return s.value
    return None


def _make_slot(*, h_open=5, m_open=0, h_fire=5, m_fire=45, grace=5, h_close=6, m_close=40):
    return JobSlot(
        window_open=time(h_open, m_open),
        fire_time=time(h_fire, m_fire),
        grace_minutes=grace,
        window_close=time(h_close, m_close),
    )


def _make_adapter(*, running=False):
    adapter = MagicMock()
    adapter.is_running.return_value = running
    adapter.start = AsyncMock()
    return adapter


def _freeze(frozen: datetime):
    mock = MagicMock(wraps=datetime)
    mock.now.return_value = frozen
    mock.combine = datetime.combine
    return patch("app.scheduler.datetime", mock)


# =============================================================================
# vtrack_collection_total
# =============================================================================

class TestCollectionTotalCounter:

    async def test_increments_on_started_outcome(self):
        slot = _make_slot()
        adapter = _make_adapter(running=True)

        with _freeze(datetime(2026, 5, 20, 5, 10, tzinfo=TZ)):
            outcome = await Scheduler()._run_and_record("ctr_started", slot, adapter)

        assert outcome == GuardianState.STARTED
        assert _sample("vtrack_collection_total_total", slot="ctr_started", outcome="started") == 1.0

    async def test_increments_on_missed_outcome(self):
        slot = _make_slot()
        adapter = _make_adapter(running=False)

        # Freeze past window_close so guardian immediately returns MISSED
        with _freeze(datetime(2026, 5, 20, 7, 0, tzinfo=TZ)):
            outcome = await Scheduler()._run_and_record("ctr_missed", slot, adapter)

        assert outcome == GuardianState.MISSED
        assert _sample("vtrack_collection_total_total", slot="ctr_missed", outcome="missed") == 1.0

    async def test_counter_label_is_slot_specific(self):
        slot = _make_slot()
        adapter = _make_adapter(running=True)

        with _freeze(datetime(2026, 5, 20, 5, 10, tzinfo=TZ)):
            await Scheduler()._run_and_record("ctr_label_check", slot, adapter)

        # Different slot should not have been incremented
        assert _sample("vtrack_collection_total_total", slot="other_slot", outcome="started") is None


# =============================================================================
# vtrack_guardian_state
# =============================================================================

class TestGuardianStateGauge:

    async def test_state_watching_is_set_to_one(self):
        slot = _make_slot()
        adapter = _make_adapter(running=False)

        # Freeze before fire_time so the guardian enters WATCHING and then polls
        # Make adapter.is_running flip to True on second call so it exits quickly
        adapter.is_running.side_effect = [False, True]
        with _freeze(datetime(2026, 5, 20, 5, 10, tzinfo=TZ)):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                await Scheduler()._watch_slot(slot, adapter, slot_name="gs_watching")

        assert _sample("vtrack_guardian_state", slot="gs_watching", state="watching") == 1.0 or \
               _sample("vtrack_guardian_state", slot="gs_watching", state="started") == 1.0

    async def test_terminal_state_started_is_one(self):
        slot = _make_slot()
        adapter = _make_adapter(running=True)

        with _freeze(datetime(2026, 5, 20, 5, 10, tzinfo=TZ)):
            await Scheduler()._watch_slot(slot, adapter, slot_name="gs_started")

        assert _sample("vtrack_guardian_state", slot="gs_started", state="started") == 1.0

    async def test_non_terminal_states_are_zero_after_started(self):
        slot = _make_slot()
        adapter = _make_adapter(running=True)

        with _freeze(datetime(2026, 5, 20, 5, 10, tzinfo=TZ)):
            await Scheduler()._watch_slot(slot, adapter, slot_name="gs_zero_check")

        assert _sample("vtrack_guardian_state", slot="gs_zero_check", state="idle") == 0.0
        assert _sample("vtrack_guardian_state", slot="gs_zero_check", state="watching") == 0.0
        assert _sample("vtrack_guardian_state", slot="gs_zero_check", state="missed") == 0.0

    async def test_terminal_state_missed_is_one(self):
        slot = _make_slot()
        adapter = _make_adapter(running=False)

        with _freeze(datetime(2026, 5, 20, 7, 0, tzinfo=TZ)):
            await Scheduler()._watch_slot(slot, adapter, slot_name="gs_missed")

        assert _sample("vtrack_guardian_state", slot="gs_missed", state="missed") == 1.0


# =============================================================================
# vtrack_collection_datapoints
# =============================================================================

class TestCollectionDatapointsHistogram:

    async def _make_stopped_manager(self, slot: str, datapoints: int) -> AsyncCollectionManager:
        manager = AsyncCollectionManager.__new__(AsyncCollectionManager)
        manager._lock = asyncio.Lock()
        manager._is_running = True
        manager._task = None
        manager._set_status_async = AsyncMock()
        manager._collection_span = None
        manager._session_lock = asyncio.Lock()
        manager._session_cookies = None
        manager._last_login_time = None
        manager._client = None
        manager._slot = slot
        state = MagicMock()
        state.get_snapshot.return_value.datapoints_collected = datapoints
        manager._state = state
        await manager.stop()
        return manager

    async def test_histogram_sum_equals_datapoints(self):
        await self._make_stopped_manager("dp_sum_test", datapoints=42)
        assert _sample("vtrack_collection_datapoints_sum", slot="dp_sum_test") == 42.0

    async def test_histogram_count_is_one_after_single_stop(self):
        await self._make_stopped_manager("dp_count_test", datapoints=10)
        assert _sample("vtrack_collection_datapoints_count", slot="dp_count_test") == 1.0

    async def test_zero_datapoints_observed(self):
        await self._make_stopped_manager("dp_zero_test", datapoints=0)
        assert _sample("vtrack_collection_datapoints_sum", slot="dp_zero_test") == 0.0
