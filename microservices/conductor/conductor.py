import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from opentelemetry import trace

from conductor.domain.ports import IContainerGateway, IVtrackGateway
from conductor.domain.resource_policy import evaluate_savings, should_stop_after_slot

logger = logging.getLogger(__name__)
_tracer = trace.get_tracer(__name__)

@dataclass(frozen=True)
class SlotConfig:
    window_open: time
    window_close: time


class Conductor:
    def __init__(
        self,
        gateway: IVtrackGateway,
        containers: IContainerGateway,
        managed_containers: list[str],
        slots: dict[str, SlotConfig],
        memory_threshold_mb: float = 256.0,
        tz: str = "America/Bogota",
        poll_interval: int = 30,
        health_timeout: int = 120,
        health_poll_interval: int = 5,
    ) -> None:
        self._gateway = gateway
        self._containers = containers
        self._managed = managed_containers
        self._slots = slots
        self._threshold = memory_threshold_mb
        self._tz = ZoneInfo(tz)
        self._poll_interval = poll_interval
        self._health_timeout = health_timeout
        self._health_poll_interval = health_poll_interval

    # ── public entry point ────────────────────────────────────────────────────

    async def run(self) -> None:
        await self.run_boot_sequence()
        while True:
            slot_name, seconds = self._next_slot_open()
            logger.info(
                "Sleeping %.0fs until %s window opens", seconds, slot_name
            )
            await asyncio.sleep(seconds)
            should_stop = await self._startup_slot(slot_name)
            await self._watch_slot(slot_name)
            if should_stop:
                await self._stop_all()
            else:
                logger.info(
                    "Containers kept running (below %.0f MB threshold)", self._threshold
                )

    # ── boot sequence ─────────────────────────────────────────────────────────

    async def run_boot_sequence(self) -> None:
        now = datetime.now(self._tz)
        active_slot = self._active_slot(now)

        if active_slot is None:
            logger.info("Boot outside collection windows — stopping managed stack")
            await self._stop_all()
            return

        logger.info("Boot inside %s window — bringing up managed stack", active_slot)
        await self._start_all()
        await self._wait_for_health()

        status = await self._gateway.guardian_status()
        slot_status = status.get(active_slot, {})
        if not slot_status.get("task_running", False):
            logger.info("Guardian not running — activating for %s slot", active_slot)
            await self._gateway.activate_guardian(active_slot)
        else:
            logger.info("Guardian already running for %s slot", active_slot)

    # ── slot startup ──────────────────────────────────────────────────────────

    async def _startup_slot(self, slot_name: str) -> bool:
        logger.info("=== Slot startup: %s ===", slot_name)

        with _tracer.start_as_current_span("conductor.container.start") as span:
            span.set_attribute("containers.count", len(self._managed))
            await self._start_all()

        with _tracer.start_as_current_span("conductor.health.wait"):
            await self._wait_for_health()

        with _tracer.start_as_current_span("conductor.guardian.activate") as span:
            span.set_attribute("slot.name", slot_name)
            await self._gateway.activate_guardian(slot_name)

        stats = [await self._containers.get_stats(n) for n in self._managed]
        summary = evaluate_savings(stats)
        decision = should_stop_after_slot(summary, self._threshold)

        with _tracer.start_as_current_span("conductor.resource.eval") as span:
            span.set_attribute("resource.total_memory_mb", round(summary.total_memory_mb, 1))
            span.set_attribute("resource.total_cpu_percent", round(summary.total_cpu_percent, 1))
            span.set_attribute("resource.decision", "stop" if decision else "keep")

        logger.info(
            "Resource snapshot: %.0f MB / %.1f%% CPU across %d containers — decision: %s",
            summary.total_memory_mb,
            summary.total_cpu_percent,
            len(stats),
            "STOP" if decision else "KEEP",
        )
        return decision

    # ── watch slot ────────────────────────────────────────────────────────────

    async def _watch_slot(self, slot_name: str) -> None:
        logger.info("Watching %s guardian until complete", slot_name)
        with _tracer.start_as_current_span("conductor.slot.watch") as span:
            while True:
                status = await self._gateway.guardian_status()
                slot_status = status.get(slot_name, {})
                if not slot_status.get("task_running", False):
                    outcome = slot_status.get("last_outcome")
                    span.set_attribute("slot.outcome", outcome or "unknown")
                    if outcome == "missed":
                        logger.warning(
                            "Guardian %s slot MISSED — collection did not fire", slot_name
                        )
                    elif outcome == "failed":
                        logger.warning(
                            "Guardian %s slot FAILED — collection ran but collected no data", slot_name
                        )
                    else:
                        logger.info(
                            "Guardian %s slot complete with outcome: %s", slot_name, outcome
                        )
                    return
                await asyncio.sleep(self._poll_interval)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _active_slot(self, now: datetime) -> str | None:
        today = now.date()
        for name, cfg in self._slots.items():
            open_dt = datetime.combine(today, cfg.window_open).replace(tzinfo=self._tz)
            close_dt = datetime.combine(today, cfg.window_close).replace(tzinfo=self._tz)
            if open_dt <= now < close_dt:
                return name
        return None

    def _next_slot_open(self) -> tuple[str, float]:
        now = datetime.now(self._tz)
        today = now.date()
        candidates = []
        for day_offset in (0, 1):
            check_date = today + timedelta(days=day_offset)
            for name, cfg in self._slots.items():
                open_dt = datetime.combine(check_date, cfg.window_open).replace(tzinfo=self._tz)
                if open_dt > now:
                    candidates.append((name, (open_dt - now).total_seconds()))
        candidates.sort(key=lambda x: x[1])
        return candidates[0]

    async def _start_all(self) -> None:
        for name in self._managed:
            await self._containers.start(name)

    async def _stop_all(self) -> None:
        for name in self._managed:
            await self._containers.stop(name)
        logger.info("Stopped %d managed containers", len(self._managed))

    async def _wait_for_health(self) -> None:
        elapsed = 0
        while True:
            if await self._gateway.health():
                logger.info("vtrack healthy after %ds", elapsed)
                return
            if elapsed >= self._health_timeout:
                logger.warning("vtrack did not become healthy within %ds", self._health_timeout)
                return
            logger.debug("vtrack not yet healthy, retrying in %ds", self._health_poll_interval)
            await asyncio.sleep(self._health_poll_interval)
            elapsed += self._health_poll_interval
