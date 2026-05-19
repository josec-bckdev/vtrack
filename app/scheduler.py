import asyncio
import logging
from datetime import datetime, time, timedelta
from enum import Enum
from zoneinfo import ZoneInfo

from app.config import JobSlot, ScheduleConfig, load_schedule_config
from app.cookie_refresh import run_refresh

logger = logging.getLogger(__name__)

GUARDIAN_POLL_INTERVAL = 30  # seconds


class GuardianState(Enum):
    IDLE = "idle"
    WATCHING = "watching"
    STARTED = "started"
    MISSED = "missed"


class Scheduler:
    """Manages scheduled collection and cookie-refresh tasks."""

    def __init__(self):
        self.morning_task: asyncio.Task | None = None
        self.afternoon_task: asyncio.Task | None = None
        self.cookie_morning_task: asyncio.Task | None = None
        self.cookie_afternoon_task: asyncio.Task | None = None
        self.morning_guardian_task: asyncio.Task | None = None
        self.afternoon_guardian_task: asyncio.Task | None = None
        self.is_running = False
        self.collection_manager = None
        self.scheduled_times_label: str = "not started"
        self._collection_status_adapter: object | None = None
        self._schedule_config: ScheduleConfig | None = None

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
        self._schedule_config = schedule_config
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

    def get_guardian_status(self) -> dict:
        def _task_running(task: asyncio.Task | None) -> bool:
            return task is not None and not task.done()

        return {
            "morning": {"task_running": _task_running(self.morning_guardian_task)},
            "afternoon": {"task_running": _task_running(self.afternoon_guardian_task)},
        }

    async def activate_guardian(self, slot_name: str, adapter) -> None:
        if self._schedule_config is None:
            raise RuntimeError("Scheduler has no schedule config — call start_scheduler first")

        if slot_name == "morning":
            if self.morning_guardian_task and not self.morning_guardian_task.done():
                raise RuntimeError("morning guardian already active")
            slot = self._schedule_config.collection_morning
            self.morning_guardian_task = asyncio.create_task(
                self._watch_slot(slot, adapter)
            )
        elif slot_name == "afternoon":
            if self.afternoon_guardian_task and not self.afternoon_guardian_task.done():
                raise RuntimeError("afternoon guardian already active")
            slot = self._schedule_config.collection_afternoon
            self.afternoon_guardian_task = asyncio.create_task(
                self._watch_slot(slot, adapter)
            )
        else:
            raise ValueError(f"Unknown slot: {slot_name!r}. Valid values: morning, afternoon")

    async def _watch_slot(self, slot: JobSlot, adapter) -> GuardianState:
        """Guardian coroutine: watches one slot and ensures the collection fires."""
        tz = ZoneInfo("America/Bogota")
        now = datetime.now(tz)
        today = now.date()

        window_open_dt = datetime.combine(today, slot.window_open).replace(tzinfo=tz)
        fire_dt = datetime.combine(today, slot.fire_time).replace(tzinfo=tz)
        grace_dt = fire_dt + timedelta(minutes=slot.grace_minutes)
        window_close_dt = datetime.combine(today, slot.window_close).replace(tzinfo=tz)

        # Already past window_close — nothing to do
        if now >= window_close_dt:
            logger.warning("Guardian: slot missed — woke after window_close (%s)", slot.window_close)
            return GuardianState.MISSED

        # Sleep until window opens
        if now < window_open_dt:
            wait = (window_open_dt - now).total_seconds()
            await asyncio.sleep(wait)

        # Watching loop — poll until a terminal state
        state = GuardianState.WATCHING
        while state == GuardianState.WATCHING:
            now = datetime.now(tz)

            if now >= window_close_dt:
                logger.warning("Guardian: slot missed — window closed with no collection started")
                return GuardianState.MISSED

            if adapter.is_running():
                logger.info("Guardian: collection already running — slot covered")
                return GuardianState.STARTED

            if now >= grace_dt:
                logger.info("Guardian: past fire+grace, starting collection")
                await adapter.start()
                return GuardianState.STARTED

            await asyncio.sleep(GUARDIAN_POLL_INTERVAL)

        return state  # unreachable, but satisfies type checkers

    async def _start_collection_if_not_running(self, schedule_type: str):
        try:
            if not self.collection_manager._is_running:
                logger.info(f"Starting {schedule_type} collection as scheduled")
                await self.collection_manager.start()
            else:
                logger.info(f"Skipping {schedule_type} collection - already running")
        except Exception as e:
            logger.error(f"Failed to start {schedule_type} collection: {e}")
