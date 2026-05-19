import os
import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Literal, Optional

import httpx
from httpx import RequestError

from app.models import (
    ScrapingResponse,
    CollectionStatusEnum,
    CollectionStatusResponse,
)
from app.database import SessionLocal
from app.domain.scraper import (
    parse_remote_datetime,
    normalize_route_data,
    should_start_collection,
    should_stop_collection,
)
from app.domain.ports import IRouteDataRepository
from shared.message_queue import MessageQueue

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
VALORES_URL = (
    "https://www.rutasljrj.net/rastreo/ljrj/admin/responsables/control/actualizaValores"
)
ESTADOS_URL = (
    "https://www.rutasljrj.net/rastreo/ljrj/admin/responsables/control/obtieneEstados"
)
RESPONSABLE_PROFILE_ID_ESTADOS = "867"
COLLECTION_INTERVAL_SECONDS = 15
SESSION_EXPIRY_HOURS = (
    1.5  # Cloudflare cookies expire at 2 hours, refresh at 1.5 to be safe
)

COOKIE_REFRESHER_URL = os.environ.get("COOKIE_REFRESHER_URL", "http://localhost:8001")
COOKIE_REFRESHER_TIMEOUT = 300  # seconds — agent loop takes ~18 steps / ~3 min

collection_manager = None


def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class AsyncCollectionManager:
    def __init__(
        self,
        message_queue: Optional[MessageQueue] = None,
        repository: Optional[IRouteDataRepository] = None,
    ):
        self._task: asyncio.Task | None = None
        self._is_running = False
        self._status: CollectionStatusEnum = CollectionStatusEnum.IDLE
        self._lock = asyncio.Lock()
        self.current_task_id: int | None = None
        self.last_data_hash: str | None = None
        self.datapoints_collected: int = 0
        self.start_time: datetime | None = None
        self.stop_time: datetime | None = None
        self.message_queue: Optional[MessageQueue] = message_queue

        # Session management
        self._last_login_time: Optional[datetime] = None
        self._session_cookies: Optional[dict] = None
        self._session_lock = asyncio.Lock()

        # Persistent httpx client to maintain session and connection pooling
        self._client: Optional[httpx.AsyncClient] = None

        # Lazy import avoids circular dependency at module load time
        if repository is None:
            from app.adapters.route_repository import SqlAlchemyRouteRepository
            repository = SqlAlchemyRouteRepository()
        self._repository: IRouteDataRepository = repository

    def _is_session_valid(self) -> bool:
        if not self._last_login_time or not self._session_cookies:
            return False
        time_since_login = (
            datetime.now(ZoneInfo("America/Bogota")) - self._last_login_time
        )
        return time_since_login < timedelta(hours=SESSION_EXPIRY_HOURS)

    async def _trigger_cookie_refresh(self) -> bool:
        logger.info("Session expired — running programmed cookie refresh")
        from app.cookie_refresh import run_refresh

        return await run_refresh(self)

    async def _ensure_valid_session(self, client: httpx.AsyncClient) -> bool:
        async with self._session_lock:
            if self._is_session_valid():
                logger.debug("Reusing valid session")
                for cookie_name, cookie_value in self._session_cookies.items():
                    client.cookies.set(cookie_name, cookie_value)
                return True

            if not await self._trigger_cookie_refresh() or not self._is_session_valid():
                logger.error("Cookie refresh did not produce a valid session")
                return False

            for cookie_name, cookie_value in self._session_cookies.items():
                client.cookies.set(cookie_name, cookie_value)
            return True

    def _get_unique_timestamp_param(self) -> dict:
        """Returns a timestamp parameter dict to bypass server-side response caching."""
        import time

        return {"_t": str(int(time.time() * 1000))}

    async def _fetch_data_with_session(
        self, client: httpx.AsyncClient
    ) -> ScrapingResponse:
        logger.info("Fetching route data...")

        # Use no-cache headers to avoid server-side or intermediate caching
        headers = {"Cache-Control": "no-cache", "Pragma": "no-cache"}

        # Add timestamp param to bypass server-side response caching
        timestamp_param = self._get_unique_timestamp_param()

        # Fetch valores data
        valores_params = timestamp_param.copy()
        valores_response = await client.post(
            VALORES_URL, headers=headers, params=valores_params
        )
        valores_response.raise_for_status()
        try:
            valores_data = valores_response.json()
            logger.debug(
                f"Valores response status: {valores_response.status_code}, data length: {len(str(valores_data))}"
            )
        except Exception as e:
            logger.warning(
                f"Failed to parse valores JSON: {e}; response_text={valores_response.text[:1000]}"
            )
            raise

        # Fetch estados data
        estados_payload = {"responsable": RESPONSABLE_PROFILE_ID_ESTADOS}
        estados_timestamp_param = self._get_unique_timestamp_param()
        estados_response = await client.post(
            ESTADOS_URL,
            data=estados_payload,
            headers=headers,
            params=estados_timestamp_param,
        )
        estados_response.raise_for_status()
        try:
            estados_data = estados_response.json()
            logger.debug(
                f"Estados response status: {estados_response.status_code}, data length: {len(str(estados_data))}"
            )
        except Exception as e:
            logger.warning(
                f"Failed to parse estados JSON: {e}; response_text={estados_response.text[:1000]}"
            )
            raise

        return ScrapingResponse(
            source="rutasljrj.net", valores_data=valores_data, estados_data=estados_data
        )

    async def _fetch_remote_data_async(self) -> ScrapingResponse:
        if self._client is None:
            self._client = httpx.AsyncClient(
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
                },
            )
            logger.info("Created persistent httpx client for session reuse")

        client = self._client

        try:
            if not await self._ensure_valid_session(client):
                raise RequestError(
                    "Session unavailable and automatic cookie refresh failed"
                )

            try:
                return await self._fetch_data_with_session(client)
            except (RequestError, httpx.HTTPStatusError) as e:
                logger.warning("Data fetch failed: %s", e)

                # Session expired mid-flight — invalidate and refresh once
                if "303" in str(e) or "Forbidden" in str(e):
                    logger.info("Session expired mid-request — triggering refresh")
                    async with self._session_lock:
                        self._session_cookies = None
                        self._last_login_time = None
                    if not await self._ensure_valid_session(client):
                        raise RequestError("Session expired and cookie refresh failed")
                    return await self._fetch_data_with_session(client)

                raise

        except Exception as e:
            logger.warning("Error during fetch, closing client: %s", e)
            if self._client:
                try:
                    await self._client.aclose()
                except Exception:
                    pass
                self._client = None
            raise

    async def _set_status_async(self, status: CollectionStatusEnum):
        self._status = status
        update_time = datetime.now(ZoneInfo("America/Bogota"))
        stop_time = None
        if status in [CollectionStatusEnum.IDLE, CollectionStatusEnum.FINISHED]:
            stop_time = update_time
            self.stop_time = stop_time
        if self.current_task_id is not None:
            self._repository.update_task_status(
                self.current_task_id, status, update_time, stop_time
            )

    def _should_start_collection(self, normalized_data: dict) -> bool:
        return should_start_collection(normalized_data)

    def _should_stop_collection(self, normalized_data: dict) -> bool:
        return should_stop_collection(normalized_data)

    def _check_data_changed(self, normalized_data: dict) -> bool:
        """Check if meaningful data has changed using a simple hash."""
        current_hash = str(
            [
                normalized_data.get("ns_latitude"),
                normalized_data.get("ew_longitude"),
                normalized_data.get("route_status"),
                normalized_data.get("student_status"),
            ]
        )

        if self.last_data_hash != current_hash:
            self.last_data_hash = current_hash
            return True
        return False

    async def _save_route_data_async(self, normalized_data: dict):
        self._repository.save_route_entry(normalized_data)
        self.datapoints_collected += 1
        if self.current_task_id is not None:
            self._repository.update_task_datapoints(
                self.current_task_id, self.datapoints_collected
            )
        logger.info(f"Saved route data for ruta {normalized_data['ruta']}")

        if self.message_queue:
            try:
                self.message_queue.push_coordinate(
                    ruta=normalized_data["ruta"],
                    latitude=normalized_data["ns_latitude"],
                    longitude=normalized_data["ew_longitude"],
                    position_ts=normalized_data.get("position_ts"),
                    route_status=normalized_data.get("route_status"),
                    student_status=normalized_data.get("student_status"),
                )
                logger.debug(
                    f"Pushed coordinate to queue for ruta {normalized_data['ruta']}"
                )
            except Exception as e:
                logger.error(f"Failed to push coordinate to queue: {e}")

    async def _collection_loop(self):
        logger.info(f"Collection loop started (Task: {self.current_task_id})")

        in_route = False

        while self._is_running:
            try:
                remote_data = await self._fetch_remote_data_async()
                normalized_data = normalize_route_data(
                    remote_data.valores_data, remote_data.estados_data
                )

                if not normalized_data:
                    await asyncio.sleep(COLLECTION_INTERVAL_SECONDS)
                    continue

                # State management
                should_start = self._should_start_collection(normalized_data)
                should_stop = self._should_stop_collection(normalized_data)

                if self._status == CollectionStatusEnum.IDLE and should_start:
                    logger.info("Starting collection - route in progress")
                    await self._set_status_async(CollectionStatusEnum.ONGOING)
                    in_route = True

                if in_route and should_stop:
                    # Save last data point
                    await self._save_route_data_async(normalized_data)
                    logger.info("Stopping collection - route completed")
                    await self.stop()
                    break

                # Save data if route is active and data changed
                if in_route and self._check_data_changed(normalized_data):
                    await self._save_route_data_async(normalized_data)

            except Exception as e:
                logger.error(f"Error in collection loop: {e}")

            await asyncio.sleep(COLLECTION_INTERVAL_SECONDS)

    async def _initialize_metadata_async(self):
        start_time = datetime.now(ZoneInfo("America/Bogota"))
        self.current_task_id = self._repository.create_task(start_time)
        self.datapoints_collected = 0
        self.start_time = start_time
        self.stop_time = None
        self.last_data_hash = None

    async def start(self) -> Literal[True]:
        async with self._lock:
            if self._is_running:
                raise RuntimeError("Collection already running")

            await self._initialize_metadata_async()
            self._is_running = True

        await self._set_status_async(CollectionStatusEnum.IDLE)
        self._task = asyncio.create_task(self._collection_loop())

        logger.info("Collection manager started")
        return True

    async def stop(self) -> Literal[True]:
        async with self._lock:
            if not self._is_running:
                return True

            self._is_running = False
            if self._task:
                self._task.cancel()
                self._task = None

        await self._set_status_async(CollectionStatusEnum.FINISHED)

        async with self._session_lock:
            self._session_cookies = None
            self._last_login_time = None

            # Close persistent client
            if self._client:
                try:
                    await self._client.aclose()
                except Exception as e:
                    logger.warning(f"Error closing httpx client: {e}")
                self._client = None

        logger.info("Collection manager stopped")
        return True

    async def get_status(self):
        """Returns the current status and metadata of the collection task."""
        if self.current_task_id is None:
            return CollectionStatusResponse(
                status=CollectionStatusEnum.IDLE, message="No active collection task"
            )

        session_status = (
            "Valid session" if self._is_session_valid() else "No valid session"
        )

        return CollectionStatusResponse(
            task_id=self.current_task_id,
            status=self._status,
            message=f"Collection {self._status.value}. {session_status}",
            start_time=self.start_time,
            stop_time=self.stop_time,
            datapoints_collected=self.datapoints_collected,
        )

    async def wait_for_completion(self):
        """Wait for the current collection task to complete."""
        if self._task:
            try:
                await self._task
            except asyncio.CancelledError:
                pass


# Initialize manager
collection_manager = AsyncCollectionManager()
