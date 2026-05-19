"""
Tests for ScheduleConfig YAML loader and Scheduler config injection.

RED phase: all tests here should fail before implementation.
"""

import pytest
import yaml
from datetime import time, datetime
from zoneinfo import ZoneInfo
from unittest.mock import MagicMock, patch

from app.config import ScheduleConfig, load_schedule_config


VALID_CONFIG = {
    "timezone": "America/Bogota",
    "schedule": {
        "cookie_refresh": {"morning": "05:40", "afternoon": "15:10"},
        "collection": {"morning": "05:45", "afternoon": "15:15"},
    },
}


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

    def test_parses_collection_morning(self, tmp_path):
        p = tmp_path / "schedule.yaml"
        p.write_text(yaml.dump(VALID_CONFIG))
        assert load_schedule_config(p).collection_morning == time(5, 45)

    def test_parses_collection_afternoon(self, tmp_path):
        p = tmp_path / "schedule.yaml"
        p.write_text(yaml.dump(VALID_CONFIG))
        assert load_schedule_config(p).collection_afternoon == time(15, 15)

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
                "collection": {"morning": "05:45", "afternoon": "15:15"},
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
    """_schedule_morning/afternoon_collection now take target_time as a param."""

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
    async def test_start_scheduler_passes_collection_morning_from_config(self):
        from unittest.mock import AsyncMock
        from app.main import Scheduler
        from app.config import ScheduleConfig

        cfg = ScheduleConfig(
            timezone="America/Bogota",
            cookie_refresh_morning=time(5, 40),
            cookie_refresh_afternoon=time(15, 10),
            collection_morning=time(7, 0),
            collection_afternoon=time(16, 0),
        )
        scheduler = Scheduler()
        scheduler.set_collection_manager(MagicMock())

        mock_morning = AsyncMock()
        mock_afternoon = AsyncMock()
        mock_cookie = AsyncMock()

        # asyncio.create_task(fn(args)) calls fn(args) synchronously to get the
        # coroutine — so call_args is recorded before the task body runs.
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
            collection_morning=time(5, 45),
            collection_afternoon=time(15, 15),
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
