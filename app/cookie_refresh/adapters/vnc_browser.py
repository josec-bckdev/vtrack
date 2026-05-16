"""VncBrowserGateway — controls the headful Chromium container via HTTP."""
import asyncio
import logging
from typing import Optional

import docker  # type: ignore
import docker.errors  # type: ignore
import httpx

from app.cookie_refresh.domain.entities import SessionCookies
from app.cookie_refresh.domain.ports import IBrowserGateway

logger = logging.getLogger(__name__)

_HEALTH_POLL_INTERVAL = 2.0
_HEALTH_TIMEOUT = 60.0


class VncBrowserGateway(IBrowserGateway):
    """
    Manages the lifecycle of the vnc-browser Docker container and drives it via
    its HTTP control API.

    Expected container endpoints:
      GET  /health          → {"status": "ok", "browser": "running"}
      POST /navigate        → {"url": str, "wait_seconds": float}
      POST /mouse/click     → {"x": int, "y": int}
      POST /mouse/double_click
      POST /mouse/triple_click
      POST /mouse/drag      → {"start_x", "start_y", "end_x", "end_y"}
      POST /keyboard/type   → {"text": str}
      POST /keyboard/key    → {"key": str}
      POST /scroll          → {"x", "y", "direction", "amount"}
      POST /mouse/right_click
      GET  /screenshot      → PNG bytes
      GET  /cookies         → {"cf_clearance": str, "ci_session": str}
    """

    def __init__(self, base_url: str, container_name: str, timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._container_name = container_name
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._docker = docker.from_env()

    async def start(self) -> None:
        logger.info("Starting VNC browser container: %s", self._container_name)
        try:
            container = self._docker.containers.get(self._container_name)
        except docker.errors.NotFound:
            raise RuntimeError(
                f"VNC browser container '{self._container_name}' not found. "
                "Run: docker compose --profile tools up vnc-browser --no-start"
            )

        if container.status != "running":
            try:
                container.start()
            except docker.errors.NotFound as exc:
                logger.warning("Container '%s' has a missing network — removing stale container", self._container_name)
                try:
                    container.remove(force=True)
                except Exception:
                    pass
                raise RuntimeError(
                    f"VNC browser container '{self._container_name}' had a stale network and was removed. "
                    "Recreate with: docker compose --profile tools up vnc-browser --no-start"
                ) from exc
            logger.info("Container started — waiting for Chromium to be ready")
        else:
            logger.info("Container already running — waiting for health check")

        await self._wait_for_health()
        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout)
        logger.info("VNC browser ready")

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.info("Stopping VNC browser container: %s", self._container_name)
        try:
            container = self._docker.containers.get(self._container_name)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: container.stop(timeout=10))
            logger.info("VNC browser container stopped")
        except docker.errors.NotFound:
            logger.warning("Container '%s' not found during stop", self._container_name)
        except Exception as exc:
            logger.warning("Failed to stop VNC browser container: %s", exc)

    async def _wait_for_health(self) -> None:
        deadline = asyncio.get_event_loop().time() + _HEALTH_TIMEOUT
        last_error: str = ""
        async with httpx.AsyncClient(base_url=self._base_url) as probe:
            while asyncio.get_event_loop().time() < deadline:
                try:
                    resp = await probe.get("/health", timeout=3.0)
                    if resp.status_code == 200 and resp.json().get("browser") == "running":
                        return
                    last_error = f"status={resp.status_code} body={resp.text[:120]}"
                except Exception as exc:
                    last_error = str(exc)
                logger.debug("VNC health check pending: %s", last_error)
                await asyncio.sleep(_HEALTH_POLL_INTERVAL)
        raise RuntimeError(
            f"VNC browser container did not become healthy within {_HEALTH_TIMEOUT}s "
            f"(last error: {last_error})"
        )

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("VncBrowserGateway.start() must be called first")
        return self._client

    async def navigate(self, url: str, wait_seconds: float = 6.0) -> None:
        await self._http().post("/navigate", json={"url": url, "wait_seconds": wait_seconds})

    async def take_screenshot(self) -> bytes:
        resp = await self._http().get("/screenshot")
        resp.raise_for_status()
        return resp.content

    async def click(self, x: int, y: int) -> None:
        await self._http().post("/mouse/click", json={"x": x, "y": y})

    async def double_click(self, x: int, y: int) -> None:
        await self._http().post("/mouse/double_click", json={"x": x, "y": y})

    async def triple_click(self, x: int, y: int) -> None:
        await self._http().post("/mouse/triple_click", json={"x": x, "y": y})

    async def type_text(self, text: str) -> None:
        await self._http().post("/keyboard/type", json={"text": text})

    async def press_key(self, key: str) -> None:
        await self._http().post("/keyboard/key", json={"key": key})

    async def scroll(self, x: int, y: int, direction: str, amount: int) -> None:
        await self._http().post("/scroll", json={"x": x, "y": y, "direction": direction, "amount": amount})

    async def right_click(self, x: int, y: int) -> None:
        await self._http().post("/mouse/right_click", json={"x": x, "y": y})

    async def left_click_drag(self, start_x: int, start_y: int, end_x: int, end_y: int) -> None:
        await self._http().post("/mouse/drag",
                                json={"start_x": start_x, "start_y": start_y, "end_x": end_x, "end_y": end_y})

    async def get_cookies(self, names: list[str]) -> SessionCookies:
        resp = await self._http().get("/cookies", params={"names": ",".join(names)})
        resp.raise_for_status()
        data = resp.json()
        return SessionCookies(cf_clearance=data["cf_clearance"], ci_session=data["ci_session"])
