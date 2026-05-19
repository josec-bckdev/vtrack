"""
Tests for ScheduleConfig YAML loader, JobSlot dataclass, and Scheduler config injection.

RED phase: all tests here should fail before implementation.
"""

import pytest
import yaml
from datetime import time, datetime
from zoneinfo import ZoneInfo
from unittest.mock import MagicMock, patch

from app.config import ScheduleConfig, load_schedule_config


# New nested YAML format with per-slot window + fire_time + grace
VALID_CONFIG = {
    "timezone": "America/Bogota",
    "schedule": {
        "cookie_refresh": {"morning": "05:40", "afternoon": "15:10"},
        "collection": {
            "morning": {
                "window_open":   "05:00",
                "fire_time":     "05:45",
                "grace_minutes": 5,
                "window_close":  "06:40",
            },
            "afternoon": {
                "window_open":   "14:30",
                "fire_time":     "15:15",
                "grace_minutes": 5,
                "window_close":  "16:30",
            },
        },
    },
}


# =============================================================================
# JobSlot contract tests
# =============================================================================

class TestJobSlotContract:

    def test_job_slot_is_importable(self):
        from app.config import JobSlot
        assert JobSlot is not None

    def test_job_slot_has_required_fields(self):
        from app.config import JobSlot
        slot = JobSlot(
            window_open=time(5, 0),
            fire_time=time(5, 45),
            grace_minutes=5,
            window_close=time(6, 40),
        )
        assert slot.window_open == time(5, 0)
        assert slot.fire_time == time(5, 45)
        assert slot.grace_minutes == 5
        assert slot.window_close == time(6, 40)

    def test_job_slot_is_frozen(self):
        from app.config import JobSlot
        slot = JobSlot(
            window_open=time(5, 0),
            fire_time=time(5, 45),
            grace_minutes=5,
            window_close=time(6, 40),
        )
        with pytest.raises((AttributeError, TypeError)):
            slot.fire_time = time(6, 0)

    def test_job_slots_are_equal_when_fields_match(self):
        from app.config import JobSlot
        a = JobSlot(time(5, 0), time(5, 45), 5, time(6, 40))
        b = JobSlot(time(5, 0), time(5, 45), 5, time(6, 40))
        assert a == b


# =============================================================================
# ScheduleConfig loader tests
# =============================================================================

class TestLoadScheduleConfig:

    def test_returns_schedule_config_instance(self, tmp_path):
        p = tmp_path / "schedule.yaml"
        p.write_text(yaml.dump(VALID_CONFIG))
        assert isinstance(load_schedule_config(p), ScheduleConfig)

    def test_parses_timezone(self, tmp_path):
        p = tmp_path / "schedule.yaml"
        p.write_text(yaml.dump(VALID_CONFIG))
        assert load_schedule_config(p).timezone == "America/Bogota"

    def test_parses_cookie_refresh_morning(self, tmp_path):
        p = tmp_path / "schedule.yaml"
        p.write_text(yaml.dump(VALID_CONFIG))
        assert load_schedule_config(p).cookie_refresh_morning == time(5, 40)

    def test_parses_cookie_refresh_afternoon(self, tmp_path):
        p = tmp_path / "schedule.yaml"
        p.write_text(yaml.dump(VALID_CONFIG))
        assert load_schedule_config(p).cookie_refresh_afternoon == time(15, 10)

    def test_parses_collection_morning_as_job_slot(self, tmp_path):
        from app.config import JobSlot
        p = tmp_path / "schedule.yaml"
        p.write_text(yaml.dump(VALID_CONFIG))
        slot = load_schedule_config(p).collection_morning
        assert isinstance(slot, JobSlot)
        assert slot.window_open == time(5, 0)
        assert slot.fire_time == time(5, 45)
        assert slot.grace_minutes == 5
        assert slot.window_close == time(6, 40)

    def test_parses_collection_afternoon_as_job_slot(self, tmp_path):
        from app.config import JobSlot
        p = tmp_path / "schedule.yaml"
        p.write_text(yaml.dump(VALID_CONFIG))
        slot = load_schedule_config(p).collection_afternoon
        assert isinstance(slot, JobSlot)
        assert slot.window_open == time(14, 30)
        assert slot.fire_time == time(15, 15)
        assert slot.grace_minutes == 5
        assert slot.window_close == time(16, 30)

    def test_missing_schedule_key_raises(self, tmp_path):
        p = tmp_path / "schedule.yaml"
        p.write_text(yaml.dump({"timezone": "America/Bogota"}))
        with pytest.raises(KeyError):
            load_schedule_config(p)

    def test_invalid_time_format_raises(self, tmp_path):
        bad = {
            "timezone": "America/Bogota",
            "schedule": {
                "cookie_refresh": {"morning": "5:40 AM", "afternoon": "15:10"},
                "collection": {
                    "morning": {
                        "window_open": "05:00", "fire_time": "05:45",
                        "grace_minutes": 5, "window_close": "06:40",
                    },
                    "afternoon": {
                        "window_open": "14:30", "fire_time": "15:15",
                        "grace_minutes": 5, "window_close": "16:30",
                    },
                },
            },
        }
        p = tmp_path / "schedule.yaml"
        p.write_text(yaml.dump(bad))
        with pytest.raises((ValueError, AttributeError)):
            load_schedule_config(p)


# =============================================================================
# Scheduler config injection tests
# =============================================================================

class TestSchedulerUsesConfigTimes:
    """_schedule_morning/afternoon_collection take fire_time extracted from JobSlot."""

    def _make_slot(self, fire_hour: int, fire_minute: int):
        from app.config import JobSlot
        return JobSlot(
            window_open=time(fire_hour - 1, 0),
            fire_time=time(fire_hour, fire_minute),
            grace_minutes=5,
            window_close=time(fire_hour + 1, 0),
        )

    @pytest.mark.asyncio
    async def test_morning_collection_uses_provided_time(self):
        from app.main import Scheduler

        scheduler = Scheduler()
        scheduler.collection_manager = MagicMock()
        scheduler.collection_manager._is_running = False

        fixed_now = datetime(2025, 1, 15, 0, 0, 0, tzinfo=ZoneInfo("America/Bogota"))
        custom_time = time(7, 30)
        expected_wait = 7 * 3600 + 30 * 60  # 7h30m from midnight

        sleep_calls = []

        async def one_shot_sleep(seconds):
            sleep_calls.append(seconds)
            scheduler.is_running = False

        with patch("app.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_now
            mock_dt.combine = datetime.combine
            with patch("asyncio.sleep", side_effect=one_shot_sleep):
                scheduler.is_running = True
                await scheduler._schedule_morning_collection(custom_time)

        assert len(sleep_calls) == 1
        assert abs(sleep_calls[0] - expected_wait) < 2

    @pytest.mark.asyncio
    async def test_afternoon_collection_uses_provided_time(self):
        from app.main import Scheduler

        scheduler = Scheduler()
        scheduler.collection_manager = MagicMock()
        scheduler.collection_manager._is_running = False

        fixed_now = datetime(2025, 1, 15, 0, 0, 0, tzinfo=ZoneInfo("America/Bogota"))
        custom_time = time(16, 0)
        expected_wait = 16 * 3600

        sleep_calls = []

        async def one_shot_sleep(seconds):
            sleep_calls.append(seconds)
            scheduler.is_running = False

        with patch("app.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_now
            mock_dt.combine = datetime.combine
            with patch("asyncio.sleep", side_effect=one_shot_sleep):
                scheduler.is_running = True
                await scheduler._schedule_afternoon_collection(custom_time)

        assert len(sleep_calls) == 1
        assert abs(sleep_calls[0] - expected_wait) < 2

    @pytest.mark.asyncio
    async def test_start_scheduler_passes_collection_morning_fire_time_from_config(self):
        from unittest.mock import AsyncMock
        from app.main import Scheduler
        from app.config import ScheduleConfig

        cfg = ScheduleConfig(
            timezone="America/Bogota",
            cookie_refresh_morning=time(5, 40),
            cookie_refresh_afternoon=time(15, 10),
            collection_morning=self._make_slot(7, 0),
            collection_afternoon=self._make_slot(16, 0),
        )
        scheduler = Scheduler()
        scheduler.set_collection_manager(MagicMock())

        mock_morning = AsyncMock()
        mock_afternoon = AsyncMock()
        mock_cookie = AsyncMock()

        with patch.object(scheduler, "_schedule_morning_collection", mock_morning), \
             patch.object(scheduler, "_schedule_afternoon_collection", mock_afternoon), \
             patch.object(scheduler, "_schedule_cookie_refresh", mock_cookie):
            await scheduler.start_scheduler(schedule_config=cfg)
            for t in (scheduler.morning_task, scheduler.afternoon_task,
                      scheduler.cookie_morning_task, scheduler.cookie_afternoon_task):
                if t:
                    t.cancel()

        mock_morning.assert_called_once_with(time(7, 0))
        mock_afternoon.assert_called_once_with(time(16, 0))

    @pytest.mark.asyncio
    async def test_start_scheduler_passes_cookie_times_from_config(self):
        from unittest.mock import AsyncMock
        from app.main import Scheduler
        from app.config import ScheduleConfig

        cfg = ScheduleConfig(
            timezone="America/Bogota",
            cookie_refresh_morning=time(6, 0),
            cookie_refresh_afternoon=time(14, 0),
            collection_morning=self._make_slot(5, 45),
            collection_afternoon=self._make_slot(15, 15),
        )
        scheduler = Scheduler()
        scheduler.set_collection_manager(MagicMock())

        mock_morning = AsyncMock()
        mock_afternoon = AsyncMock()
        mock_cookie = AsyncMock()

        with patch.object(scheduler, "_schedule_morning_collection", mock_morning), \
             patch.object(scheduler, "_schedule_afternoon_collection", mock_afternoon), \
             patch.object(scheduler, "_schedule_cookie_refresh", mock_cookie):
            await scheduler.start_scheduler(schedule_config=cfg)
            for t in (scheduler.morning_task, scheduler.afternoon_task,
                      scheduler.cookie_morning_task, scheduler.cookie_afternoon_task):
                if t:
                    t.cancel()

        mock_cookie.assert_any_call(time(6, 0), "morning")
        mock_cookie.assert_any_call(time(14, 0), "afternoon")
