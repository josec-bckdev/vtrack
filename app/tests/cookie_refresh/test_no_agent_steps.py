"""Unit tests for NoAgentStepsUseCase — mocks at IBrowserGateway and IVtrackGateway ports."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.cookie_refresh.application.no_agent_steps import NoAgentStepsUseCase
from app.cookie_refresh.domain.entities import (
    FailureReason, ProgrammedScript, ProgrammedStep, RunMode, SessionCookies,
)
from app.cookie_refresh.domain.ports import IBrowserGateway, IVtrackGateway


def _make_browser(cookies: SessionCookies | None = None) -> IBrowserGateway:
    """Return an IBrowserGateway mock that yields the given cookies on get_cookies."""
    browser = AsyncMock(spec=IBrowserGateway)
    browser.get_cookies = AsyncMock(return_value=cookies)
    return browser


def _make_vtrack(success: bool = True) -> IVtrackGateway:
    vtrack = AsyncMock(spec=IVtrackGateway)
    vtrack.post_cookies = AsyncMock(return_value=success)
    return vtrack


def _script(*steps: ProgrammedStep) -> ProgrammedScript:
    return ProgrammedScript(steps=list(steps))


CLICK = ProgrammedStep(action_type="left_click", params={"coordinate": [100, 200]}, delay_after_ms=0.0)
TYPE_EMAIL = ProgrammedStep(action_type="type", params={"text": "{{email}}"}, delay_after_ms=0.0)
TYPE_PASSWORD = ProgrammedStep(action_type="type", params={"text": "{{password}}"}, delay_after_ms=0.0)
GET_COOKIES = ProgrammedStep(action_type="get_cookies", params={"names": ["cf_clearance", "ci_session"]})
VALID_COOKIES = SessionCookies(cf_clearance="cf_abc", ci_session="ci_xyz")


@pytest.mark.asyncio
class TestNoAgentStepsUseCase:
    async def test_successful_run_returns_ok_result(self):
        browser = _make_browser(cookies=VALID_COOKIES)
        vtrack = _make_vtrack(success=True)
        script = _script(CLICK, GET_COOKIES)

        use_case = NoAgentStepsUseCase(browser, vtrack, script,
                                       login_url="https://example.com",
                                       login_email="user@test.com",
                                       login_password="secret")
        result = await use_case.execute()

        assert result.success is True
        assert result.cookies == VALID_COOKIES
        assert result.mode == RunMode.PROGRAMMED
        assert result.steps_taken == 2

    async def test_starts_and_closes_browser(self):
        browser = _make_browser(cookies=VALID_COOKIES)
        vtrack = _make_vtrack()
        use_case = NoAgentStepsUseCase(browser, vtrack, _script(GET_COOKIES),
                                       login_url="https://example.com",
                                       login_email="u", login_password="p")
        await use_case.execute()

        browser.start.assert_called_once()
        browser.close.assert_called_once()

    async def test_browser_closed_even_when_get_cookies_raises(self):
        browser = _make_browser()
        browser.get_cookies = AsyncMock(side_effect=RuntimeError("network error"))
        vtrack = _make_vtrack()
        use_case = NoAgentStepsUseCase(browser, vtrack, _script(GET_COOKIES),
                                       login_url="https://example.com",
                                       login_email="u", login_password="p")
        result = await use_case.execute()

        browser.close.assert_called_once()
        assert result.success is False
        assert result.failure_reason == FailureReason.NO_COOKIES

    async def test_no_get_cookies_step_returns_failure(self):
        browser = _make_browser()
        vtrack = _make_vtrack()
        use_case = NoAgentStepsUseCase(browser, vtrack, _script(CLICK),
                                       login_url="https://example.com",
                                       login_email="u", login_password="p")
        result = await use_case.execute()

        assert result.success is False
        assert result.failure_reason == FailureReason.NO_COOKIES

    async def test_vtrack_rejection_returns_failure(self):
        browser = _make_browser(cookies=VALID_COOKIES)
        vtrack = _make_vtrack(success=False)
        use_case = NoAgentStepsUseCase(browser, vtrack, _script(GET_COOKIES),
                                       login_url="https://example.com",
                                       login_email="u", login_password="p")
        result = await use_case.execute()

        assert result.success is False
        assert result.failure_reason == FailureReason.VTRACK_POST_FAILED

    async def test_email_placeholder_resolved(self):
        browser = _make_browser(cookies=VALID_COOKIES)
        vtrack = _make_vtrack()
        use_case = NoAgentStepsUseCase(browser, vtrack, _script(TYPE_EMAIL, GET_COOKIES),
                                       login_url="https://example.com",
                                       login_email="real@email.com", login_password="pw")
        await use_case.execute()

        browser.type_text.assert_called_once_with("real@email.com")

    async def test_password_placeholder_resolved(self):
        browser = _make_browser(cookies=VALID_COOKIES)
        vtrack = _make_vtrack()
        use_case = NoAgentStepsUseCase(browser, vtrack, _script(TYPE_PASSWORD, GET_COOKIES),
                                       login_url="https://example.com",
                                       login_email="u", login_password="supersecret")
        await use_case.execute()

        browser.type_text.assert_called_once_with("supersecret")

    async def test_step_after_get_cookies_not_executed(self):
        """get_cookies stops the loop — subsequent steps are never dispatched."""
        extra_click = ProgrammedStep(action_type="left_click", params={"coordinate": [1, 1]})
        browser = _make_browser(cookies=VALID_COOKIES)
        vtrack = _make_vtrack()
        use_case = NoAgentStepsUseCase(browser, vtrack, _script(GET_COOKIES, extra_click),
                                       login_url="https://example.com",
                                       login_email="u", login_password="p")
        await use_case.execute()

        browser.click.assert_not_called()

    async def test_vtrack_receives_extracted_cookies(self):
        browser = _make_browser(cookies=VALID_COOKIES)
        vtrack = _make_vtrack()
        use_case = NoAgentStepsUseCase(browser, vtrack, _script(GET_COOKIES),
                                       login_url="https://example.com",
                                       login_email="u", login_password="p")
        await use_case.execute()

        vtrack.post_cookies.assert_called_once_with(VALID_COOKIES)
