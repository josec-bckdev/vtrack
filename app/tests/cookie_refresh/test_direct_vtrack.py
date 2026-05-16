"""Unit tests for DirectVtrackGateway."""
import pytest
from datetime import datetime
from unittest.mock import MagicMock

from app.cookie_refresh.adapters.direct_vtrack import DirectVtrackGateway
from app.cookie_refresh.domain.entities import SessionCookies


def _make_collection_manager():
    cm = MagicMock()
    cm._session_cookies = None
    cm._last_login_time = None
    return cm


COOKIES = SessionCookies(cf_clearance="cf_abc", ci_session="ci_xyz")


@pytest.mark.asyncio
class TestDirectVtrackGateway:
    async def test_post_cookies_writes_to_collection_manager(self):
        cm = _make_collection_manager()
        gateway = DirectVtrackGateway(cm)

        result = await gateway.post_cookies(COOKIES)

        assert result is True
        assert cm._session_cookies == {"cf_clearance": "cf_abc", "ci_session": "ci_xyz"}

    async def test_post_cookies_sets_login_time(self):
        cm = _make_collection_manager()
        gateway = DirectVtrackGateway(cm)

        before = datetime.now()
        await gateway.post_cookies(COOKIES)
        after = datetime.now()

        assert cm._last_login_time is not None
        assert before <= cm._last_login_time.replace(tzinfo=None) <= after

    async def test_post_cookies_returns_false_on_error(self):
        cm = MagicMock()
        cm._session_cookies = property(fset=MagicMock(side_effect=RuntimeError("write failed")))

        # Simulate attribute set raising via __setattr__
        type(cm).__setattr__ = MagicMock(side_effect=RuntimeError("write failed"))

        gateway = DirectVtrackGateway(cm)
        result = await gateway.post_cookies(COOKIES)

        assert result is False
