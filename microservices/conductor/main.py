import asyncio
import logging
import os
from datetime import time

from conductor.adapters.container_gateway import DockerContainerGateway
from conductor.adapters.vtrack_gateway import HttpxVtrackGateway
from conductor.conductor import Conductor, SlotConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


def _parse_time(value: str) -> time:
    h, m = value.strip().split(":")
    return time(int(h), int(m))


def _load_slots() -> dict[str, SlotConfig]:
    return {
        "morning": SlotConfig(
            window_open=_parse_time(os.environ.get("SLOT_MORNING_WINDOW_OPEN", "05:00")),
            window_close=_parse_time(os.environ.get("SLOT_MORNING_WINDOW_CLOSE", "06:40")),
        ),
        "afternoon": SlotConfig(
            window_open=_parse_time(os.environ.get("SLOT_AFTERNOON_WINDOW_OPEN", "14:30")),
            window_close=_parse_time(os.environ.get("SLOT_AFTERNOON_WINDOW_CLOSE", "16:30")),
        ),
    }


async def main() -> None:
    gateway = HttpxVtrackGateway(
        base_url=os.environ.get("VTRACK_BASE_URL", "http://api:8000")
    )
    containers = DockerContainerGateway()
    managed = [
        c.strip()
        for c in os.environ.get(
            "MANAGED_CONTAINERS", "api,db,redis,alert-processor,notification-sender"
        ).split(",")
        if c.strip()
    ]
    slots = _load_slots()
    threshold = float(os.environ.get("MEMORY_THRESHOLD_MB", "256"))
    tz = os.environ.get("TZ", "America/Bogota")

    logger.info(
        "Conductor starting — managed: %s | slots: %s | threshold: %.0f MB",
        managed,
        {k: f"{v.window_open}–{v.window_close}" for k, v in slots.items()},
        threshold,
    )

    conductor = Conductor(
        gateway=gateway,
        containers=containers,
        managed_containers=managed,
        slots=slots,
        memory_threshold_mb=threshold,
        tz=tz,
    )
    await conductor.run()


if __name__ == "__main__":
    asyncio.run(main())
