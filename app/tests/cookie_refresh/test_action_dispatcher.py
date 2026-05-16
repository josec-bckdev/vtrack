"""Unit tests for ActionDispatcher — covers all action type branches."""
import pytest
from unittest.mock import AsyncMock

from app.cookie_refresh.application.no_agent_steps import ActionDispatcher
from app.cookie_refresh.domain.ports import IBrowserGateway


def _browser() -> IBrowserGateway:
    return AsyncMock(spec=IBrowserGateway)


@pytest.mark.asyncio
class TestActionDispatcher:
    async def test_left_click_calls_browser_click(self):
        browser = _browser()
        dispatcher = ActionDispatcher(browser)
        await dispatcher.dispatch({"action": "left_click", "coordinate": [100, 200]})
        browser.click.assert_called_once_with(100, 200)

    async def test_double_click_calls_browser_double_click(self):
        browser = _browser()
        dispatcher = ActionDispatcher(browser)
        await dispatcher.dispatch({"action": "double_click", "coordinate": [50, 75]})
        browser.double_click.assert_called_once_with(50, 75)

    async def test_triple_click_calls_browser_triple_click(self):
        browser = _browser()
        dispatcher = ActionDispatcher(browser)
        await dispatcher.dispatch({"action": "triple_click", "coordinate": [10, 20]})
        browser.triple_click.assert_called_once_with(10, 20)

    async def test_type_calls_browser_type_text(self):
        browser = _browser()
        dispatcher = ActionDispatcher(browser)
        await dispatcher.dispatch({"action": "type", "text": "hello world"})
        browser.type_text.assert_called_once_with("hello world")

    async def test_key_calls_browser_press_key(self):
        browser = _browser()
        dispatcher = ActionDispatcher(browser)
        await dispatcher.dispatch({"action": "key", "text": "Return"})
        browser.press_key.assert_called_once_with("Return")

    async def test_scroll_calls_browser_scroll_with_defaults(self):
        browser = _browser()
        dispatcher = ActionDispatcher(browser)
        await dispatcher.dispatch({"action": "scroll", "coordinate": [300, 400]})
        browser.scroll.assert_called_once_with(300, 400, "down", 3)

    async def test_scroll_calls_browser_scroll_with_explicit_values(self):
        browser = _browser()
        dispatcher = ActionDispatcher(browser)
        await dispatcher.dispatch({
            "action": "scroll", "coordinate": [0, 0],
            "direction": "up", "amount": 5,
        })
        browser.scroll.assert_called_once_with(0, 0, "up", 5)

    async def test_right_click_calls_browser_right_click(self):
        browser = _browser()
        dispatcher = ActionDispatcher(browser)
        await dispatcher.dispatch({"action": "right_click", "coordinate": [80, 90]})
        browser.right_click.assert_called_once_with(80, 90)

    async def test_left_click_drag_calls_browser_drag(self):
        browser = _browser()
        dispatcher = ActionDispatcher(browser)
        await dispatcher.dispatch({
            "action": "left_click_drag",
            "start_coordinate": [10, 20],
            "coordinate": [100, 200],
        })
        browser.left_click_drag.assert_called_once_with(10, 20, 100, 200)

    async def test_wait_sleeps_for_duration(self):
        browser = _browser()
        dispatcher = ActionDispatcher(browser)
        # Use a very short duration so the test stays fast
        result = await dispatcher.dispatch({"action": "wait", "duration": 1})
        assert "wait" in result

    async def test_screenshot_returns_image_block(self):
        browser = _browser()
        browser.take_screenshot = AsyncMock(return_value=b"\x89PNG...")
        dispatcher = ActionDispatcher(browser)
        result = await dispatcher.dispatch({"action": "screenshot"})
        assert isinstance(result, list)
        assert result[0]["type"] == "image"
        assert result[0]["source"]["type"] == "base64"

    async def test_unknown_action_returns_unsupported_string(self):
        browser = _browser()
        dispatcher = ActionDispatcher(browser)
        result = await dispatcher.dispatch({"action": "teleport"})
        assert "unsupported" in str(result).lower()
