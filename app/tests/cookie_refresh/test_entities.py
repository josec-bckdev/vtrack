"""Unit tests for cookie_refresh domain entities."""
import pytest
from app.cookie_refresh.domain.entities import (
    AgentResult, FailureReason, ProgrammedScript, ProgrammedStep, RunMode, SessionCookies,
)


class TestSessionCookies:
    def test_valid_cookies_created(self):
        cookies = SessionCookies(cf_clearance="abc123", ci_session="sess456")
        assert cookies.cf_clearance == "abc123"
        assert cookies.ci_session == "sess456"

    def test_empty_cf_clearance_raises(self):
        with pytest.raises(ValueError, match="cf_clearance"):
            SessionCookies(cf_clearance="", ci_session="sess456")

    def test_whitespace_cf_clearance_raises(self):
        with pytest.raises(ValueError, match="cf_clearance"):
            SessionCookies(cf_clearance="   ", ci_session="sess456")

    def test_empty_ci_session_raises(self):
        with pytest.raises(ValueError, match="ci_session"):
            SessionCookies(cf_clearance="abc123", ci_session="")

    def test_whitespace_ci_session_raises(self):
        with pytest.raises(ValueError, match="ci_session"):
            SessionCookies(cf_clearance="abc123", ci_session="  ")

    def test_cookies_are_immutable(self):
        cookies = SessionCookies(cf_clearance="abc", ci_session="def")
        with pytest.raises(Exception):
            cookies.cf_clearance = "changed"  # type: ignore[misc]


class TestAgentResult:
    def test_ok_result_has_success_true(self):
        cookies = SessionCookies(cf_clearance="cf", ci_session="ci")
        result = AgentResult.ok(cookies, steps_taken=5, mode=RunMode.PROGRAMMED)
        assert result.success is True
        assert result.cookies == cookies
        assert result.steps_taken == 5
        assert result.mode == RunMode.PROGRAMMED
        assert result.error is None

    def test_ok_result_requires_cookies(self):
        with pytest.raises(ValueError):
            AgentResult.ok(None, steps_taken=1)  # type: ignore[arg-type]

    def test_fail_result_has_success_false(self):
        result = AgentResult.fail("something broke", steps_taken=3,
                                  mode=RunMode.PROGRAMMED, failure_reason=FailureReason.NO_COOKIES)
        assert result.success is False
        assert result.error == "something broke"
        assert result.steps_taken == 3
        assert result.failure_reason == FailureReason.NO_COOKIES
        assert result.cookies is None

    def test_fail_result_requires_error_message(self):
        with pytest.raises(ValueError):
            AgentResult.fail("", steps_taken=1)


class TestProgrammedEntities:
    def test_programmed_step_defaults(self):
        step = ProgrammedStep(action_type="left_click", params={"coordinate": [100, 200]})
        assert step.delay_after_ms == 0.0

    def test_programmed_step_with_delay(self):
        step = ProgrammedStep(action_type="type", params={"text": "hello"}, delay_after_ms=500.0)
        assert step.delay_after_ms == 500.0

    def test_programmed_script_holds_steps(self):
        steps = [
            ProgrammedStep(action_type="left_click", params={"coordinate": [10, 20]}),
            ProgrammedStep(action_type="get_cookies", params={"names": ["cf_clearance"]}),
        ]
        script = ProgrammedScript(steps=steps)
        assert len(script.steps) == 2
        assert script.steps[0].action_type == "left_click"
