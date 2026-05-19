"""Failing tests for HttpxVtrackGateway — mocks httpx, no network."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from conductor.adapters.vtrack_gateway import HttpxVtrackGateway


BASE = "http://api:8000"


@pytest.fixture
def gateway():
    return HttpxVtrackGateway(base_url=BASE)


class TestHealth:
    async def test_returns_true_on_200(self, gateway):
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("conductor.adapters.vtrack_gateway.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            result = await gateway.health()

        assert result is True

    async def test_returns_false_on_non_200(self, gateway):
        mock_resp = MagicMock()
        mock_resp.status_code = 503

        with patch("conductor.adapters.vtrack_gateway.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            result = await gateway.health()

        assert result is False

    async def test_returns_false_on_connection_error(self, gateway):
        with patch("conductor.adapters.vtrack_gateway.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=Exception("connection refused"))
            mock_client_cls.return_value = mock_client

            result = await gateway.health()

        assert result is False


class TestGuardianStatus:
    async def test_returns_parsed_json(self, gateway):
        payload = {"morning": {"task_running": True, "current_state": "watching"}}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = payload

        with patch("conductor.adapters.vtrack_gateway.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            result = await gateway.guardian_status()

        assert result == payload

    async def test_raises_on_http_error(self, gateway):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.raise_for_status.side_effect = Exception("server error")

        with patch("conductor.adapters.vtrack_gateway.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            with pytest.raises(Exception):
                await gateway.guardian_status()


class TestActivateGuardian:
    async def test_posts_to_correct_url(self, gateway):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()

        with patch("conductor.adapters.vtrack_gateway.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            await gateway.activate_guardian("morning")

            mock_client.post.assert_called_once_with(
                f"{BASE}/monitor/guardian/activate",
                params={"slot": "morning"},
            )

    async def test_raises_on_http_error(self, gateway):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("conflict")

        with patch("conductor.adapters.vtrack_gateway.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            with pytest.raises(Exception):
                await gateway.activate_guardian("morning")


class TestCollectionStatus:
    async def test_returns_parsed_json(self, gateway):
        payload = {"collection_running": False}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = payload
        mock_resp.raise_for_status = MagicMock()

        with patch("conductor.adapters.vtrack_gateway.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            result = await gateway.collection_status()

        assert result == payload
