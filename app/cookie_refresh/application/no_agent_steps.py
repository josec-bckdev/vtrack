"""NoAgentStepsUseCase — zero-AI path that replays programmed browser steps."""
from __future__ import annotations

import asyncio
import base64
import logging
import random
from typing import Optional

from app.cookie_refresh.domain.entities import (
    AgentResult, FailureReason, ProgrammedScript, RunMode, SessionCookies,
)
from app.cookie_refresh.domain.ports import IBrowserGateway, IVtrackGateway

logger = logging.getLogger(__name__)


class ActionDispatcher:
    """Translates step action types into browser gateway calls."""

    def __init__(self, browser: IBrowserGateway) -> None:
        self._browser = browser

    async def dispatch(self, action: dict) -> object:
        action_type = action.get("action", "")

        if action_type == "screenshot":
            data = await self._browser.take_screenshot()
            return [{"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                  "data": base64.b64encode(data).decode()}}]
        if action_type == "left_click":
            x, y = action["coordinate"]
            await self._browser.click(x, y)
        elif action_type == "double_click":
            x, y = action["coordinate"]
            await self._browser.double_click(x, y)
        elif action_type == "triple_click":
            x, y = action["coordinate"]
            await self._browser.triple_click(x, y)
        elif action_type == "type":
            await self._browser.type_text(action["text"])
        elif action_type == "key":
            await self._browser.press_key(action["text"])
        elif action_type == "scroll":
            x, y = action["coordinate"]
            await self._browser.scroll(x, y, action.get("direction", "down"), action.get("amount", 3))
        elif action_type == "right_click":
            x, y = action["coordinate"]
            await self._browser.right_click(x, y)
        elif action_type == "left_click_drag":
            sx, sy = action["start_coordinate"]
            ex, ey = action["coordinate"]
            await self._browser.left_click_drag(sx, sy, ex, ey)
        elif action_type == "wait":
            await asyncio.sleep(action.get("duration", 1000) / 1000)
        else:
            logger.warning("Unsupported action type: %s", action_type)
            return f"unsupported action: {action_type}"
        return f"{action_type} executed"


class NoAgentStepsUseCase:
    def __init__(
        self,
        browser: IBrowserGateway,
        vtrack: IVtrackGateway,
        script: ProgrammedScript,
        login_url: str,
        login_email: str,
        login_password: str,
        randomness_pct: float = 0.0,
    ) -> None:
        self._browser = browser
        self._vtrack = vtrack
        self._script = script
        self._login_url = login_url
        self._login_email = login_email
        self._login_password = login_password
        self._randomness_pct = randomness_pct
        self._dispatcher = ActionDispatcher(browser)

    async def execute(self) -> AgentResult:
        logger.info("Programmed mode: %d steps, zero AI calls", len(self._script.steps))
        try:
            await self._browser.start()
            return await self._run()
        finally:
            await self._browser.close()

    async def _run(self) -> AgentResult:
        await self._browser.navigate(self._login_url)
        cookies: Optional[SessionCookies] = None
        steps_taken = 0

        for step in self._script.steps:
            if step.action_type == "get_cookies":
                names = step.params.get("names", [])
                try:
                    cookies = await self._browser.get_cookies(names)
                except Exception as exc:
                    logger.error("get_cookies failed: %s", exc)
                    return AgentResult.fail(str(exc), steps_taken=steps_taken + 1,
                                           mode=RunMode.PROGRAMMED, failure_reason=FailureReason.NO_COOKIES)
                steps_taken += 1
                break

            params = self._resolve_credentials(step.params, step.action_type)
            await self._dispatcher.dispatch({**params, "action": step.action_type})
            if step.delay_after_ms > 0:
                await asyncio.sleep(self._jitter(step.delay_after_ms) / 1000)
            steps_taken += 1

        return await self._finalise(cookies, steps_taken)

    async def _finalise(self, cookies: Optional[SessionCookies], steps: int) -> AgentResult:
        if cookies is None:
            return AgentResult.fail("No get_cookies step executed", steps_taken=steps,
                                    mode=RunMode.PROGRAMMED, failure_reason=FailureReason.NO_COOKIES)
        logger.info("Cookies retrieved — writing to vtrack")
        posted = await self._vtrack.post_cookies(cookies)
        if not posted:
            return AgentResult.fail("Cookies retrieved but vtrack rejected them", steps_taken=steps,
                                    mode=RunMode.PROGRAMMED, failure_reason=FailureReason.VTRACK_POST_FAILED)
        logger.info("Programmed session succeeded in %d steps", steps)
        return AgentResult.ok(cookies, steps_taken=steps, mode=RunMode.PROGRAMMED)

    def _resolve_credentials(self, params: dict, action_type: str) -> dict:
        if action_type == "type":
            text = params.get("text", "")
            if text == "{{email}}":
                return {**params, "text": self._login_email}
            if text == "{{password}}":
                return {**params, "text": self._login_password}
        return params

    def _jitter(self, ms: float) -> float:
        factor = 1.0 + random.uniform(-self._randomness_pct, self._randomness_pct)
        return max(0.0, ms * factor)
