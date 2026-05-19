"""
Tests for the _watch_slot guardian state machine in app/scheduler.py.

The guardian runs one coroutine per slot per day. It follows this state machine:

  IDLE
    │  (now >= window_open)
    ▼
  WATCHING ── poll every 30 s ──► collection already running? → STARTED
    │
    │  (now >= fire_time + grace_minutes AND not running)
    ▼
  SELF_STARTED  (guardian called adapter.start())
    │
    │  (now >= window_close AND never started)
    ▼
  MISSED  (log warning, return)

All tests freeze time via a controllable async clock and inject a mock
ICollectionStatusAdapter. No real asyncio.sleep is ever called.
"""

import pytest
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import AsyncMock, MagicMock, patch, call


TZ = ZoneInfo("America/Bogota")


def _dt(h: int, m: int, s: int = 0) -> datetime:
    """Return a Bogota datetime on a fixed reference date."""
    return datetime(2026, 5, 20, h, m, s, tzinfo=TZ)


def _make_slot(window_open: time, fire_time: time, grace: int, window_close: time):
    from app.config import JobSlot
    return JobSlot(
        window_open=window_open,
        fire_time=fire_time,
        grace_minutes=grace,
        window_close=window_close,
    )


MORNING_SLOT = _make_slot(time(5, 0), time(5, 45), 5, time(6, 40))


# =============================================================================
# Import check
# =============================================================================

class TestGuardianImports:

    def test_watch_slot_method_exists_on_scheduler(self):
        from app.scheduler import Scheduler
        assert hasattr(Scheduler, "_watch_slot")

    def test_guardian_state_enum_is_importable(self):
        from app.scheduler import GuardianState
        assert GuardianState is not None

    def test_guardian_state_has_required_values(self):
        from app.scheduler import GuardianState
        assert hasattr(GuardianState, "IDLE")
        assert hasattr(GuardianState, "WATCHING")
        assert hasattr(GuardianState, "STARTED")
        assert hasattr(GuardianState, "MISSED")


# =============================================================================
# State machine: before window opens
# =============================================================================

class TestGuardianBeforeWindow:

    @pytest.mark.asyncio
    async def test_sleeps_until_window_open_when_before_window(self):
        """Guardian sleeps from pre-window time until window_open."""
        from app.scheduler import Scheduler
        from app.domain.ports import ICollectionStatusAdapter

        scheduler = Scheduler()
        mock_adapter = MagicMock(spec=ICollectionStatusAdapter)
        mock_adapter.is_running.return_value = False

        # Now is 04:00 — 60 minutes before window_open (05:00)
        now = _dt(4, 0)
        expected_wait = 60 * 60  # 3600 s

        sleep_calls = []

        async def one_shot_sleep(seconds):
            sleep_calls.append(seconds)
            # After sleeping we're past window_close — stop the guardian
            nonlocal now
            now = _dt(7, 0)

        with patch("app.scheduler.datetime") as mock_dt, \
             patch("asyncio.sleep", side_effect=one_shot_sleep):
            mock_dt.now.side_effect = lambda tz=None: now
            mock_dt.combine = datetime.combine
            await scheduler._watch_slot(MORNING_SLOT, mock_adapter)

        assert len(sleep_calls) >= 1
        assert abs(sleep_calls[0] - expected_wait) < 2


# =============================================================================
# State machine: collection starts by itself (WATCHING → STARTED)
# =============================================================================

class TestGuardianWatchingToStarted:

    @pytest.mark.asyncio
    async def test_transitions_to_started_when_collection_already_running(self):
        """When the collection starts externally, guardian exits without calling adapter.start."""
        from app.scheduler import Scheduler
        from app.domain.ports import ICollectionStatusAdapter

        scheduler = Scheduler()
        mock_adapter = MagicMock(spec=ICollectionStatusAdapter)
        mock_adapter.start = AsyncMock()

        # Clock values: [initial check, loop iter 1 (before grace), loop iter 2 (before grace)]
        # _watch_slot calls datetime.now() once at the top (init) then once per loop iteration.
        clock = [_dt(5, 20), _dt(5, 40), _dt(5, 40)]
        clock_iter = iter(clock)

        # iter 1: not running yet; iter 2: running (started externally)
        mock_adapter.is_running.side_effect = [False, True]

        sleep_calls = []

        async def fake_sleep(seconds):
            sleep_calls.append(seconds)

        with patch("app.scheduler.datetime") as mock_dt, \
             patch("asyncio.sleep", side_effect=fake_sleep):
            mock_dt.now.side_effect = lambda tz=None: next(clock_iter, _dt(7, 0))
            mock_dt.combine = datetime.combine
            await scheduler._watch_slot(MORNING_SLOT, mock_adapter)

        # start() must NOT have been called — it started on its own
        mock_adapter.start.assert_not_awaited()


# =============================================================================
# State machine: guardian fires (WATCHING → SELF_STARTED)
# =============================================================================

class TestGuardianSelfStart:

    @pytest.mark.asyncio
    async def test_calls_adapter_start_after_fire_time_plus_grace(self):
        """Guardian fires adapter.start() when past fire_time+grace and not running."""
        from app.scheduler import Scheduler
        from app.domain.ports import ICollectionStatusAdapter

        scheduler = Scheduler()
        mock_adapter = MagicMock(spec=ICollectionStatusAdapter)
        mock_adapter.start = AsyncMock()

        # fire_time=05:45, grace=5 min → guardian fires at 05:50
        # Provide two identical timestamps: [initial check, loop iteration 1]
        clock = [_dt(5, 51), _dt(5, 51)]
        clock_iter = iter(clock)
        mock_adapter.is_running.return_value = False

        async def fake_sleep(seconds):
            pass

        with patch("app.scheduler.datetime") as mock_dt, \
             patch("asyncio.sleep", side_effect=fake_sleep):
            mock_dt.now.side_effect = lambda tz=None: next(clock_iter, _dt(7, 0))
            mock_dt.combine = datetime.combine
            await scheduler._watch_slot(MORNING_SLOT, mock_adapter)

        mock_adapter.start.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_does_not_call_start_before_grace_expires(self):
        """Guardian does not fire before fire_time + grace_minutes."""
        from app.scheduler import Scheduler
        from app.domain.ports import ICollectionStatusAdapter

        scheduler = Scheduler()
        mock_adapter = MagicMock(spec=ICollectionStatusAdapter)
        mock_adapter.start = AsyncMock()

        # fire_time=05:45, grace=5 → threshold is 05:50
        # Now is 05:47 — inside the grace window
        clock = iter([_dt(5, 47), _dt(7, 0)])
        mock_adapter.is_running.return_value = False

        async def fake_sleep(seconds):
            pass

        with patch("app.scheduler.datetime") as mock_dt, \
             patch("asyncio.sleep", side_effect=fake_sleep):
            mock_dt.now.side_effect = lambda tz=None: next(clock, _dt(7, 0))
            mock_dt.combine = datetime.combine
            await scheduler._watch_slot(MORNING_SLOT, mock_adapter)

        mock_adapter.start.assert_not_awaited()


# =============================================================================
# State machine: MISSED
# =============================================================================

class TestGuardianMissed:

    @pytest.mark.asyncio
    async def test_exits_without_starting_when_past_window_close(self):
        """When now >= window_close and nothing ran, guardian records MISSED and exits."""
        from app.scheduler import Scheduler
        from app.domain.ports import ICollectionStatusAdapter

        scheduler = Scheduler()
        mock_adapter = MagicMock(spec=ICollectionStatusAdapter)
        mock_adapter.start = AsyncMock()
        mock_adapter.is_running.return_value = False

        # Simulate starting past window_close=06:40
        clock = iter([_dt(7, 0)])

        async def fake_sleep(seconds):
            pass

        with patch("app.scheduler.datetime") as mock_dt, \
             patch("asyncio.sleep", side_effect=fake_sleep):
            mock_dt.now.side_effect = lambda tz=None: next(clock, _dt(7, 0))
            mock_dt.combine = datetime.combine
            await scheduler._watch_slot(MORNING_SLOT, mock_adapter)

        mock_adapter.start.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_missed_is_logged(self, caplog):
        """A missed slot emits at least one WARNING log."""
        import logging
        from app.scheduler import Scheduler
        from app.domain.ports import ICollectionStatusAdapter

        scheduler = Scheduler()
        mock_adapter = MagicMock(spec=ICollectionStatusAdapter)
        mock_adapter.start = AsyncMock()
        mock_adapter.is_running.return_value = False

        clock = iter([_dt(7, 0)])

        async def fake_sleep(seconds):
            pass

        with patch("app.scheduler.datetime") as mock_dt, \
             patch("asyncio.sleep", side_effect=fake_sleep):
            mock_dt.now.side_effect = lambda tz=None: next(clock, _dt(7, 0))
            mock_dt.combine = datetime.combine
            with caplog.at_level(logging.WARNING, logger="app.scheduler"):
                await scheduler._watch_slot(MORNING_SLOT, mock_adapter)

        assert any("miss" in r.message.lower() or "missed" in r.message.lower()
                   for r in caplog.records)


# =============================================================================
# Outcome tracking — get_guardian_status reflects last completed run
# =============================================================================

class TestGuardianOutcomeTracking:

    def test_initial_status_has_no_outcome(self):
        from app.scheduler import Scheduler
        scheduler = Scheduler()
        status = scheduler.get_guardian_status()
        assert status["morning"]["last_outcome"] is None
        assert status["afternoon"]["last_outcome"] is None

    def test_initial_status_has_no_completed_at(self):
        from app.scheduler import Scheduler
        scheduler = Scheduler()
        status = scheduler.get_guardian_status()
        assert status["morning"]["completed_at"] is None
        assert status["afternoon"]["completed_at"] is None

    @pytest.mark.asyncio
    async def test_status_records_started_outcome_after_self_start(self):
        """After guardian fires, get_guardian_status shows last_outcome=started."""
        from app.scheduler import Scheduler, GuardianState
        from app.domain.ports import ICollectionStatusAdapter
        from app.config import JobSlot, ScheduleConfig

        scheduler = Scheduler()
        slot = JobSlot(time(5, 0), time(5, 45), 5, time(6, 40))
        scheduler._schedule_config = ScheduleConfig(
            timezone="America/Bogota",
            cookie_refresh_morning=time(5, 40),
            cookie_refresh_afternoon=time(15, 10),
            collection_morning=slot,
            collection_afternoon=slot,
        )
        mock_adapter = MagicMock(spec=ICollectionStatusAdapter)
        mock_adapter.start = AsyncMock()
        mock_adapter.is_running.return_value = False

        clock = iter([_dt(5, 51), _dt(5, 51)])

        async def fake_sleep(s): pass

        with patch("app.scheduler.datetime") as mock_dt, \
             patch("asyncio.sleep", side_effect=fake_sleep):
            mock_dt.now.side_effect = lambda tz=None: next(clock, _dt(7, 0))
            mock_dt.combine = datetime.combine
            await scheduler.activate_guardian("morning", mock_adapter)
            # Wait for the background task to complete
            if scheduler.morning_guardian_task:
                await scheduler.morning_guardian_task

        status = scheduler.get_guardian_status()
        assert status["morning"]["last_outcome"] == GuardianState.STARTED.value

    @pytest.mark.asyncio
    async def test_status_records_missed_outcome_after_window_close(self):
        """After a missed slot, get_guardian_status shows last_outcome=missed."""
        from app.scheduler import Scheduler, GuardianState
        from app.domain.ports import ICollectionStatusAdapter
        from app.config import JobSlot, ScheduleConfig

        scheduler = Scheduler()
        slot = JobSlot(time(5, 0), time(5, 45), 5, time(6, 40))
        scheduler._schedule_config = ScheduleConfig(
            timezone="America/Bogota",
            cookie_refresh_morning=time(5, 40),
            cookie_refresh_afternoon=time(15, 10),
            collection_morning=slot,
            collection_afternoon=slot,
        )
        mock_adapter = MagicMock(spec=ICollectionStatusAdapter)
        mock_adapter.start = AsyncMock()
        mock_adapter.is_running.return_value = False

        clock = iter([_dt(7, 0)])

        async def fake_sleep(s): pass

        with patch("app.scheduler.datetime") as mock_dt, \
             patch("asyncio.sleep", side_effect=fake_sleep):
            mock_dt.now.side_effect = lambda tz=None: next(clock, _dt(7, 0))
            mock_dt.combine = datetime.combine
            await scheduler.activate_guardian("morning", mock_adapter)
            if scheduler.morning_guardian_task:
                await scheduler.morning_guardian_task

        status = scheduler.get_guardian_status()
        assert status["morning"]["last_outcome"] == GuardianState.MISSED.value

    @pytest.mark.asyncio
    async def test_status_records_completed_at_timestamp(self):
        """completed_at is a non-None string after a guardian run finishes."""
        from app.scheduler import Scheduler
        from app.domain.ports import ICollectionStatusAdapter
        from app.config import JobSlot, ScheduleConfig

        scheduler = Scheduler()
        slot = JobSlot(time(5, 0), time(5, 45), 5, time(6, 40))
        scheduler._schedule_config = ScheduleConfig(
            timezone="America/Bogota",
            cookie_refresh_morning=time(5, 40),
            cookie_refresh_afternoon=time(15, 10),
            collection_morning=slot,
            collection_afternoon=slot,
        )
        mock_adapter = MagicMock(spec=ICollectionStatusAdapter)
        mock_adapter.start = AsyncMock()
        mock_adapter.is_running.return_value = False

        clock = iter([_dt(7, 0)])

        async def fake_sleep(s): pass

        with patch("app.scheduler.datetime") as mock_dt, \
             patch("asyncio.sleep", side_effect=fake_sleep):
            mock_dt.now.side_effect = lambda tz=None: next(clock, _dt(7, 0))
            mock_dt.combine = datetime.combine
            await scheduler.activate_guardian("morning", mock_adapter)
            if scheduler.morning_guardian_task:
                await scheduler.morning_guardian_task

        status = scheduler.get_guardian_status()
        assert status["morning"]["completed_at"] is not None

    @pytest.mark.asyncio
    async def test_afternoon_outcome_independent_of_morning(self):
        """morning and afternoon outcomes are tracked independently."""
        from app.scheduler import Scheduler, GuardianState
        from app.domain.ports import ICollectionStatusAdapter
        from app.config import JobSlot, ScheduleConfig

        scheduler = Scheduler()
        slot = JobSlot(time(5, 0), time(5, 45), 5, time(6, 40))
        scheduler._schedule_config = ScheduleConfig(
            timezone="America/Bogota",
            cookie_refresh_morning=time(5, 40),
            cookie_refresh_afternoon=time(15, 10),
            collection_morning=slot,
            collection_afternoon=slot,
        )
        mock_adapter = MagicMock(spec=ICollectionStatusAdapter)
        mock_adapter.start = AsyncMock()
        mock_adapter.is_running.return_value = False

        clock = iter([_dt(7, 0)])

        async def fake_sleep(s): pass

        with patch("app.scheduler.datetime") as mock_dt, \
             patch("asyncio.sleep", side_effect=fake_sleep):
            mock_dt.now.side_effect = lambda tz=None: next(clock, _dt(7, 0))
            mock_dt.combine = datetime.combine
            await scheduler.activate_guardian("morning", mock_adapter)
            if scheduler.morning_guardian_task:
                await scheduler.morning_guardian_task

        status = scheduler.get_guardian_status()
        assert status["morning"]["last_outcome"] == GuardianState.MISSED.value
        assert status["afternoon"]["last_outcome"] is None
