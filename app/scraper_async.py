import os
import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Literal, Optional

import httpx
from sqlalchemy.orm import Session
from httpx import RequestError

from app.models import (
    ScrapingResponse, CollectionStatusEnum, 
    RouteDataEntry, CollectionMetadata, CollectionStatusResponse
)
from app.database import SessionLocal

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
LOGIN_URL = "https://www.rutasljrj.net/rastreo/ljrj/login/validacion"
VALORES_URL = "https://www.rutasljrj.net/rastreo/ljrj/admin/responsables/control/actualizaValores"
ESTADOS_URL = "https://www.rutasljrj.net/rastreo/ljrj/admin/responsables/control/obtieneEstados"
RESPONSABLE_PROFILE_ID = "35"
COLLECTION_INTERVAL_SECONDS = 15
SESSION_EXPIRY_HOURS = 12

SCRAPER_EMAIL = os.environ.get("SCRAPER_EMAIL")
SCRAPER_PASSWORD = os.environ.get("SCRAPER_PASSWORD")

collection_manager = None

def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def parse_remote_datetime(date_string: str) -> datetime | None:
    if '0000-00-00' in date_string:
        return None
    try:
        naive_dt = datetime.strptime(date_string, '%Y-%m-%d %H:%M:%S')
        return naive_dt.replace(tzinfo=ZoneInfo("America/Bogota"))
    except ValueError:
        logger.warning(f"Failed to parse datetime: {date_string}")
        return None

def normalize_route_data(valores_data: list, estados_data: list) -> Optional[dict]:
    """Normalize scraped data into structured format."""
    if not valores_data or not estados_data:
        return None
        
    first_valores = valores_data[0]
    first_estados = estados_data[0]

    if not first_valores or not first_estados:
        return None

    try:
        return {
            'ruta': int(first_valores[0]),
            'ns_latitude': float(first_valores[2]),
            'ew_longitude': float(first_valores[3]),
            'position_ts': parse_remote_datetime(first_valores[5]),
            'route_status': first_estados[1],
            'route_status_ts': parse_remote_datetime(first_estados[2]),
            'student_status': first_estados[5],
            'student_status_ts': parse_remote_datetime(first_estados[6]),
        }
    except (ValueError, IndexError, TypeError) as e:
        logger.error(f"Error normalizing data: {e}")
        return None

class AsyncCollectionManager:
    def __init__(self):
        self._task: asyncio.Task | None = None
        self._is_running = False
        self._status: CollectionStatusEnum = CollectionStatusEnum.IDLE
        self._lock = asyncio.Lock()
        self.current_task_id: int | None = None
        self.last_data_hash: str | None = None
        self.datapoints_collected: int = 0
        self.start_time: datetime | None = None
        self.stop_time: datetime | None = None
        
        # Session management
        self._last_login_time: Optional[datetime] = None
        self._session_cookies: Optional[dict] = None
        self._session_lock = asyncio.Lock()

    async def _login_async(self, client: httpx.AsyncClient) -> bool:
        login_data = {
            'correo': SCRAPER_EMAIL,
            'clave': SCRAPER_PASSWORD,
            'perfil': RESPONSABLE_PROFILE_ID
        }
        
        logger.info(f"Logging in to {LOGIN_URL}...")
        login_response = await client.post(LOGIN_URL, data=login_data)
        
        if login_response.status_code in [200, 303]:
            logger.info("Login successful")
            self._last_login_time = datetime.now(ZoneInfo("America/Bogota"))
            self._session_cookies = dict(login_response.cookies)
            return True
        
        logger.error(f"Login failed: {login_response.status_code}")
        return False

    def _is_session_valid(self) -> bool:
        if not self._last_login_time or not self._session_cookies:
            return False
        time_since_login = datetime.now(ZoneInfo("America/Bogota")) - self._last_login_time
        return time_since_login < timedelta(hours=SESSION_EXPIRY_HOURS)

    async def _ensure_valid_session(self, client: httpx.AsyncClient) -> bool:
        async with self._session_lock:
            if self._is_session_valid():
                logger.debug("Reusing valid session")
                for cookie_name, cookie_value in self._session_cookies.items():
                    client.cookies.set(cookie_name, cookie_value)
                return True
            else:
                logger.info("Performing fresh login")
                return await self._login_async(client)

    async def _fetch_data_with_session(self, client: httpx.AsyncClient) -> ScrapingResponse:
        logger.info("Fetching route data...")
        
        # Fetch valores data
        valores_response = await client.post(VALORES_URL)
        valores_response.raise_for_status()
        valores_data = valores_response.json()

        # Fetch estados data
        estados_payload = {'responsable': RESPONSABLE_PROFILE_ID}
        estados_response = await client.post(ESTADOS_URL, data=estados_payload)
        estados_response.raise_for_status()
        estados_data = estados_response.json()

        return ScrapingResponse(
            source="rutasljrj.net",
            valores_data=valores_data,
            estados_data=estados_data
        )

    async def _fetch_remote_data_async(self) -> ScrapingResponse:
        if not SCRAPER_EMAIL or not SCRAPER_PASSWORD:
            raise RuntimeError("Missing scraper credentials")

        async with httpx.AsyncClient(follow_redirects=False) as client:
            if not await self._ensure_valid_session(client):
                raise RequestError("Failed to establish valid session")

            try:
                return await self._fetch_data_with_session(client)
            except (RequestError, httpx.HTTPStatusError) as e:
                logger.warning(f"Data fetch failed, re-logging in: {e}")
                async with self._session_lock:
                    self._session_cookies = None
                    self._last_login_time = None
                
                if not await self._ensure_valid_session(client):
                    raise RequestError("Failed to re-establish session")
                
                return await self._fetch_data_with_session(client)

    async def _set_status_async(self, status: CollectionStatusEnum):
        self._status = status
        
        db_gen = get_db_session()
        db = next(db_gen)
        
        try:
            if self.current_task_id is not None:
                metadata = db.query(CollectionMetadata).get(self.current_task_id)
                if metadata:
                    metadata.status = self._status.value
                    metadata.last_update_time = datetime.now(ZoneInfo("America/Bogota"))
                    
                    if status in [CollectionStatusEnum.IDLE, CollectionStatusEnum.FINISHED]:
                        metadata.stop_time = datetime.now(ZoneInfo("America/Bogota"))
                        self.stop_time = metadata.stop_time
                    
                    db.commit()
        finally:
            db.close()

    def _should_start_collection(self, normalized_data: dict) -> bool:
        return normalized_data.get('route_status') == "En recorrido"

    def _should_stop_collection(self, normalized_data: dict) -> bool:
        student_status = normalized_data.get('student_status', '')
        current_hour = datetime.now(ZoneInfo("America/Bogota")).hour
        
        pm_delivered = (student_status == "Bajo") and (current_hour > 12)
        am_onboard = (student_status == "Subio") and (current_hour <= 12)
        return pm_delivered or am_onboard

    def _check_data_changed(self, normalized_data: dict) -> bool:
        """Check if meaningful data has changed using a simple hash."""
        current_hash = str([
            normalized_data.get('ns_latitude'),
            normalized_data.get('ew_longitude'), 
            normalized_data.get('route_status'),
            normalized_data.get('student_status')
        ])
        
        if self.last_data_hash != current_hash:
            self.last_data_hash = current_hash
            return True
        return False

    async def _save_route_data_async(self, normalized_data: dict):
        db_gen = get_db_session()
        db = next(db_gen)
        
        try:
            route_entry = RouteDataEntry(**normalized_data)
            db.add(route_entry)
            db.commit()
            
            self.datapoints_collected += 1
            if self.current_task_id is not None:
                metadata = db.query(CollectionMetadata).get(self.current_task_id)
                if metadata:
                    metadata.datapoints_count = self.datapoints_collected
                    db.commit()
            
            logger.info(f"Saved route data for ruta {normalized_data['ruta']}")
            
        except Exception as e:
            logger.error(f"Error saving route data: {e}")
            db.rollback()
            raise
        finally:
            db.close()

    async def _collection_loop(self):
        logger.info(f"Collection loop started (Task: {self.current_task_id})")
        
        in_route = False
        
        while self._is_running:
            try:
                remote_data = await self._fetch_remote_data_async()
                normalized_data = normalize_route_data(
                    remote_data.valores_data, 
                    remote_data.estados_data
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
                    return

                # Save data if route is active and data changed
                if in_route and self._check_data_changed(normalized_data):
                    await self._save_route_data_async(normalized_data)

            except Exception as e:
                logger.error(f"Error in collection loop: {e}")
                
            await asyncio.sleep(COLLECTION_INTERVAL_SECONDS)

    async def _initialize_metadata_async(self):
        db_gen = get_db_session()
        db = next(db_gen)
        
        try:
            metadata_entry = CollectionMetadata(
                start_time=datetime.now(ZoneInfo("America/Bogota")),
                status=CollectionStatusEnum.IDLE.value,
                last_update_time=datetime.now(ZoneInfo("America/Bogota"))
            )
            db.add(metadata_entry)
            db.commit()
            
            self.current_task_id = metadata_entry.id
            self.datapoints_collected = 0
            self.start_time = metadata_entry.start_time
            self.stop_time = None
            self.last_data_hash = None
            
        finally:
            db.close()

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
        
        logger.info("Collection manager stopped")
        return True

    async def get_status(self):
        """Returns the current status and metadata of the collection task."""
        if self.current_task_id is None:
            return CollectionStatusResponse(
                status=CollectionStatusEnum.IDLE,
                message="No active collection task"
            )
            
        session_status = "Valid session" if self._is_session_valid() else "No valid session"
            
        return CollectionStatusResponse(
            task_id=self.current_task_id,
            status=self._status,
            message=f"Collection {self._status.value}. {session_status}",
            start_time=self.start_time,
            stop_time=self.stop_time,
            datapoints_collected=self.datapoints_collected
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