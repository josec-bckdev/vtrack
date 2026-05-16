"""Unit tests for VncBrowserGateway — Docker and httpx mocked at the boundary."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from app.cookie_refresh.adapters.vnc_browser import VncBrowserGateway
from app.cookie_refresh.domain.entities import SessionCookies


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_gateway(base_url: str = "http://vnc-browser:8080",
                  container_name: str = "vnc_browser") -> VncBrowserGateway:
    with patch("app.cookie_refresh.adapters.vnc_browser.docker.from_env"):
        return VncBrowserGateway(base_url=base_url, container_name=container_name)


def _running_container() -> MagicMock:
    container = MagicMock()
    container.status = "running"
    return container


def _stopped_container() -> MagicMock:
    container = MagicMock()
    container.status = "stopped"
    return container


def _healthy_probe_response() -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"status": "ok", "browser": "running"}
    return resp


# ---------------------------------------------------------------------------
# Lifecycle — start / close
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestVncBrowserGatewayLifecycle:
    async def test_start_with_already_running_container_skips_start_call(self):
        gw = _make_gateway()
        gw._docker.containers.get.return_value = _running_container()

        with patch.object(gw, "_wait_for_health", new=AsyncMock()):
            with patch("httpx.AsyncClient"):
                await gw.start()

        gw._docker.containers.get.return_value.start.assert_not_called()

    async def test_start_with_stopped_container_calls_start(self):
        gw = _make_gateway()
        container = _stopped_container()
        gw._docker.containers.get.return_value = container

        with patch.object(gw, "_wait_for_health", new=AsyncMock()):
            with patch("httpx.AsyncClient"):
                await gw.start()

        container.start.assert_called_once()

    async def test_start_raises_when_container_not_found(self):
        import docker.errors
        gw = _make_gateway()
        gw._docker.containers.get.side_effect = docker.errors.NotFound("not found")

        with pytest.raises(RuntimeError, match="not found"):
            await gw.start()

    async def test_close_stops_running_container(self):
        gw = _make_gateway()
        mock_client = AsyncMock()
        gw._client = mock_client
        container = _running_container()
        gw._docker.containers.get.return_value = container

        await gw.close()

        mock_client.aclose.assert_called_once()
        container.stop.assert_called_once()

    async def test_close_is_safe_when_container_already_gone(self):
        import docker.errors
        gw = _make_gateway()
        gw._client = AsyncMock()
        gw._docker.containers.get.side_effect = docker.errors.NotFound("gone")

        await gw.close()  # must not raise


# ---------------------------------------------------------------------------
# Browser action methods — each calls the correct httpx endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestVncBrowserGatewayActions:
    def _gw_with_client(self) -> tuple[VncBrowserGateway, AsyncMock]:
        gw = _make_gateway()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=MagicMock(status_code=200))
        mock_client.get = AsyncMock(return_value=MagicMock(
            status_code=200, content=b"\x89PNG..."
        ))
        gw._client = mock_client
        return gw, mock_client

    async def test_navigate_posts_to_navigate_endpoint(self):
        gw, client = self._gw_with_client()
        await gw.navigate("https://example.com", wait_seconds=3.0)
        client.post.assert_called_once_with(
            "/navigate", json={"url": "https://example.com", "wait_seconds": 3.0}
        )

    async def test_click_posts_to_mouse_click(self):
        gw, client = self._gw_with_client()
        await gw.click(100, 200)
        client.post.assert_called_once_with("/mouse/click", json={"x": 100, "y": 200})

    async def test_double_click_posts_to_mouse_double_click(self):
        gw, client = self._gw_with_client()
        await gw.double_click(50, 60)
        client.post.assert_called_once_with("/mouse/double_click", json={"x": 50, "y": 60})

    async def test_triple_click_posts_to_mouse_triple_click(self):
        gw, client = self._gw_with_client()
        await gw.triple_click(10, 20)
        client.post.assert_called_once_with("/mouse/triple_click", json={"x": 10, "y": 20})

    async def test_type_text_posts_to_keyboard_type(self):
        gw, client = self._gw_with_client()
        await gw.type_text("hello")
        client.post.assert_called_once_with("/keyboard/type", json={"text": "hello"})

    async def test_press_key_posts_to_keyboard_key(self):
        gw, client = self._gw_with_client()
        await gw.press_key("Return")
        client.post.assert_called_once_with("/keyboard/key", json={"key": "Return"})

    async def test_scroll_posts_to_scroll_endpoint(self):
        gw, client = self._gw_with_client()
        await gw.scroll(0, 0, "down", 3)
        client.post.assert_called_once_with(
            "/scroll", json={"x": 0, "y": 0, "direction": "down", "amount": 3}
        )

    async def test_right_click_posts_to_mouse_right_click(self):
        gw, client = self._gw_with_client()
        await gw.right_click(30, 40)
        client.post.assert_called_once_with("/mouse/right_click", json={"x": 30, "y": 40})

    async def test_left_click_drag_posts_to_mouse_drag(self):
        gw, client = self._gw_with_client()
        await gw.left_click_drag(0, 0, 100, 200)
        client.post.assert_called_once_with(
            "/mouse/drag",
            json={"start_x": 0, "start_y": 0, "end_x": 100, "end_y": 200},
        )

    async def test_take_screenshot_returns_bytes(self):
        gw, client = self._gw_with_client()
        result = await gw.take_screenshot()
        assert result == b"\x89PNG..."

    async def test_get_cookies_returns_session_cookies(self):
        gw, client = self._gw_with_client()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"cf_clearance": "cf_val", "ci_session": "ci_val"}
        mock_resp.raise_for_status = MagicMock()
        client.get = AsyncMock(return_value=mock_resp)

        cookies = await gw.get_cookies(["cf_clearance", "ci_session"])

        assert isinstance(cookies, SessionCookies)
        assert cookies.cf_clearance == "cf_val"
        assert cookies.ci_session == "ci_val"

    async def test_http_raises_when_client_not_started(self):
        gw = _make_gateway()
        with pytest.raises(RuntimeError, match="start\\(\\)"):
            await gw.navigate("https://example.com")


# ---------------------------------------------------------------------------
# close() — additional paths
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestVncBrowserGatewayClose:
    async def test_close_when_client_is_none_still_stops_container(self):
        gw = _make_gateway()
        assert gw._client is None
        container = _running_container()
        gw._docker.containers.get.return_value = container

        await gw.close()

        container.stop.assert_called_once()

    async def test_close_handles_generic_stop_exception(self):
        gw = _make_gateway()
        gw._client = AsyncMock()
        container = _running_container()
        container.stop.side_effect = RuntimeError("unexpected")
        gw._docker.containers.get.return_value = container

        await gw.close()  # must not raise


# ---------------------------------------------------------------------------
# start() — stale network path (container.start() raises NotFound)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestVncBrowserGatewayStaleNetwork:
    async def test_start_removes_stale_container_and_raises(self):
        import docker.errors
        gw = _make_gateway()
        container = _stopped_container()
        container.start.side_effect = docker.errors.NotFound("network gone")
        gw._docker.containers.get.return_value = container

        with pytest.raises(RuntimeError, match="stale network"):
            await gw.start()

        container.remove.assert_called_once()


# ---------------------------------------------------------------------------
# _wait_for_health()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestWaitForHealth:
    async def test_returns_when_container_is_healthy(self):
        gw = _make_gateway()

        healthy_resp = MagicMock()
        healthy_resp.status_code = 200
        healthy_resp.json.return_value = {"browser": "running"}

        mock_probe = AsyncMock()
        mock_probe.get = AsyncMock(return_value=healthy_resp)
        mock_probe.__aenter__ = AsyncMock(return_value=mock_probe)
        mock_probe.__aexit__ = AsyncMock(return_value=False)

        with patch("app.cookie_refresh.adapters.vnc_browser.httpx.AsyncClient",
                   return_value=mock_probe):
            await gw._wait_for_health()  # must not raise

    async def test_raises_when_health_check_times_out(self):
        gw = _make_gateway()

        mock_probe = AsyncMock()
        mock_probe.get = AsyncMock(side_effect=Exception("refused"))
        mock_probe.__aenter__ = AsyncMock(return_value=mock_probe)
        mock_probe.__aexit__ = AsyncMock(return_value=False)

        call_count = 0

        def _time():
            nonlocal call_count
            call_count += 1
            # First call: set deadline. Subsequent calls: already past deadline.
            return 0.0 if call_count == 1 else 999.0

        mock_loop = MagicMock()
        mock_loop.time.side_effect = _time

        with patch("app.cookie_refresh.adapters.vnc_browser.httpx.AsyncClient",
                   return_value=mock_probe), \
             patch("asyncio.get_event_loop", return_value=mock_loop):
            with pytest.raises(RuntimeError, match="healthy"):
                await gw._wait_for_health()
