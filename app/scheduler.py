import asyncio
import logging
from datetime import datetime, time
from zoneinfo import ZoneInfo

from app.config import ScheduleConfig, load_schedule_config
from app.cookie_refresh import run_refresh

logger = logging.getLogger(__name__)


class Scheduler:
    """Manages scheduled collection and cookie-refresh tasks."""

    def __init__(self):
        self.morning_task: asyncio.Task | None = None
        self.afternoon_task: asyncio.Task | None = None
        self.cookie_morning_task: asyncio.Task | None = None
        self.cookie_afternoon_task: asyncio.Task | None = None
        self.is_running = False
        self.collection_manager = None
        self.scheduled_times_label: str = "not started"

    def set_collection_manager(self, manager):
        self.collection_manager = manager

    async def start_scheduler(self, schedule_config: ScheduleConfig | None = None):
        """Start all scheduled tasks using times from schedule_config (or schedule.yaml)."""
        if self.is_running:
            logger.info("Scheduler is already running")
            return

        if not self.collection_manager:
            logger.error("Collection manager not set for scheduler")
            return

        if schedule_config is None:
            from pathlib import Path
            _default_path = Path(__file__).parent / "schedule.yaml"
            schedule_config = load_schedule_config(_default_path)

        self.is_running = True
        morning_fire = schedule_config.collection_morning.fire_time
        afternoon_fire = schedule_config.collection_afternoon.fire_time
        self.scheduled_times_label = (
            f"cookie refresh {schedule_config.cookie_refresh_morning.strftime('%H:%M')} / "
            f"{schedule_config.cookie_refresh_afternoon.strftime('%H:%M')}, "
            f"collection {morning_fire.strftime('%H:%M')} / "
            f"{afternoon_fire.strftime('%H:%M')}"
        )
        logger.info("Starting collection scheduler...")

        self.morning_task = asyncio.create_task(
            self._schedule_morning_collection(morning_fire)
        )
        self.afternoon_task = asyncio.create_task(
            self._schedule_afternoon_collection(afternoon_fire)
        )
        self.cookie_morning_task = asyncio.create_task(
            self._schedule_cookie_refresh(schedule_config.cookie_refresh_morning, "morning")
        )
        self.cookie_afternoon_task = asyncio.create_task(
            self._schedule_cookie_refresh(schedule_config.cookie_refresh_afternoon, "afternoon")
        )

        logger.info(
            "Schedulers started — cookie refresh at %s / %s, collection at %s / %s",
            schedule_config.cookie_refresh_morning.strftime("%H:%M"),
            schedule_config.cookie_refresh_afternoon.strftime("%H:%M"),
            morning_fire.strftime("%H:%M"),
            afternoon_fire.strftime("%H:%M"),
        )

    async def stop_scheduler(self):
        """Stop all scheduled tasks."""
        self.is_running = False

        for task in (self.morning_task, self.afternoon_task,
                     self.cookie_morning_task, self.cookie_afternoon_task):
            if task:
                task.cancel()
        self.morning_task = self.afternoon_task = None
        self.cookie_morning_task = self.cookie_afternoon_task = None

        logger.info("Collection scheduler stopped")

    async def _schedule_morning_collection(self, target_time: time):
        while self.is_running:
            now = datetime.now(ZoneInfo("America/Bogota"))
            next_run = datetime.combine(now.date(), target_time).replace(tzinfo=ZoneInfo("America/Bogota"))
            if now >= next_run:
                next_run = next_run.replace(day=next_run.day + 1)
            wait_seconds = (next_run - now).total_seconds()
            logger.info("Morning collection scheduled for %s at %s (%.0fs from now)",
                        next_run.date(), target_time.strftime("%H:%M"), wait_seconds)
            await asyncio.sleep(wait_seconds)
            if self.is_running:
                await self._start_collection_if_not_running("morning")

    async def _schedule_afternoon_collection(self, target_time: time):
        while self.is_running:
            now = datetime.now(ZoneInfo("America/Bogota"))
            next_run = datetime.combine(now.date(), target_time).replace(tzinfo=ZoneInfo("America/Bogota"))
            if now >= next_run:
                next_run = next_run.replace(day=next_run.day + 1)
            wait_seconds = (next_run - now).total_seconds()
            logger.info("Afternoon collection scheduled for %s at %s (%.0fs from now)",
                        next_run.date(), target_time.strftime("%H:%M"), wait_seconds)
            await asyncio.sleep(wait_seconds)
            if self.is_running:
                await self._start_collection_if_not_running("afternoon")

    async def _schedule_cookie_refresh(self, target_time: time, label: str):
        while self.is_running:
            now = datetime.now(ZoneInfo("America/Bogota"))
            next_run = datetime.combine(now.date(), target_time).replace(tzinfo=ZoneInfo("America/Bogota"))
            if now >= next_run:
                next_run = next_run.replace(day=next_run.day + 1)
            wait_seconds = (next_run - now).total_seconds()
            logger.info("Cookie refresh (%s) at %s scheduled for %s (%.0fs from now)",
                        label, target_time.strftime("%H:%M"), next_run, wait_seconds)
            await asyncio.sleep(wait_seconds)
            if self.is_running and self.collection_manager is not None:
                try:
                    logger.info("Running proactive cookie refresh (%s)", label)
                    await run_refresh(self.collection_manager)
                except Exception as exc:
                    logger.error("Proactive cookie refresh (%s) failed: %s", label, exc)

    async def _start_collection_if_not_running(self, schedule_type: str):
        try:
            if not self.collection_manager._is_running:
                logger.info(f"Starting {schedule_type} collection as scheduled")
                await self.collection_manager.start()
            else:
                logger.info(f"Skipping {schedule_type} collection - already running")
        except Exception as e:
            logger.error(f"Failed to start {schedule_type} collection: {e}")
