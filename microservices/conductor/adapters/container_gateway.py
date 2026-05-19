import asyncio
import logging
from functools import partial

import docker
import docker.errors

from conductor.domain.ports import ContainerStats, IContainerGateway

logger = logging.getLogger(__name__)


def _get_client():
    return docker.from_env()


def _sync_is_running(name: str) -> bool:
    try:
        client = _get_client()
        container = client.containers.get(name)
        container.reload()
        return container.status == "running"
    except Exception:
        return False


def _sync_start(name: str) -> None:
    client = _get_client()
    container = client.containers.get(name)
    container.reload()
    if container.status != "running":
        container.start()
        logger.info("Started container %s", name)
    else:
        logger.debug("Container %s already running, skipping start", name)


def _sync_stop(name: str) -> None:
    client = _get_client()
    container = client.containers.get(name)
    container.reload()
    if container.status == "running":
        container.stop()
        logger.info("Stopped container %s", name)
    else:
        logger.debug("Container %s not running, skipping stop", name)


def _sync_get_stats(name: str) -> ContainerStats:
    client = _get_client()
    container = client.containers.get(name)
    raw = container.stats(stream=False)

    memory_bytes: int = raw["memory_stats"].get("usage", 0)

    cpu_delta = (
        raw["cpu_stats"]["cpu_usage"]["total_usage"]
        - raw["precpu_stats"]["cpu_usage"]["total_usage"]
    )
    system_delta = (
        raw["cpu_stats"].get("system_cpu_usage", 0)
        - raw["precpu_stats"].get("system_cpu_usage", 0)
    )
    online_cpus = raw["cpu_stats"].get("online_cpus", 1)

    if system_delta > 0:
        cpu_percent = (cpu_delta / system_delta) * online_cpus * 100.0
    else:
        cpu_percent = 0.0

    return ContainerStats(name=name, memory_bytes=memory_bytes, cpu_percent=max(0.0, cpu_percent))


class DockerContainerGateway(IContainerGateway):
    async def _run(self, fn, *args):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, partial(fn, *args))

    async def is_running(self, name: str) -> bool:
        return await self._run(_sync_is_running, name)

    async def start(self, name: str) -> None:
        await self._run(_sync_start, name)

    async def stop(self, name: str) -> None:
        await self._run(_sync_stop, name)

    async def get_stats(self, name: str) -> ContainerStats:
        return await self._run(_sync_get_stats, name)
