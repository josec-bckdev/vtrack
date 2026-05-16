"""DirectVtrackGateway — writes cookies directly onto the in-process collection_manager."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from app.cookie_refresh.domain.entities import SessionCookies
from app.cookie_refresh.domain.ports import IVtrackGateway

if TYPE_CHECKING:
    from app.scraper_async import AsyncCollectionManager

logger = logging.getLogger(__name__)


class DirectVtrackGateway(IVtrackGateway):
    """
    Delivers refreshed cookies straight to the AsyncCollectionManager instance
    instead of making an HTTP call back to the /session/set-cookies endpoint.
    """

    def __init__(self, collection_manager: "AsyncCollectionManager") -> None:
        self._cm = collection_manager

    async def post_cookies(self, cookies: SessionCookies) -> bool:
        try:
            self._cm._session_cookies = {
                "cf_clearance": cookies.cf_clearance,
                "ci_session": cookies.ci_session,
            }
            self._cm._last_login_time = datetime.now(ZoneInfo("America/Bogota"))
            logger.info("Cookies written directly to collection_manager (cf_clearance, ci_session)")
            return True
        except Exception as exc:
            logger.error("Failed to write cookies to collection_manager: %s", exc)
            return False
