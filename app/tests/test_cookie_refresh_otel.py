"""RED tests — cookie_refresh.run OTel span.

Verifies that run_refresh() emits a cookie_refresh.run span with
refresh.success and refresh.steps_taken attributes.

Fails until app/cookie_refresh/__init__.py is instrumented.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.cookie_refresh import run_refresh


def _make_manager():
    return MagicMock()


def _mock_use_case(*, success: bool, steps: int):
    """Return a patched NoAgentStepsUseCase that returns the given result."""
    from app.cookie_refresh.domain.entities import AgentResult, RunMode
    result = AgentResult.ok(
        cookies=MagicMock(), steps_taken=steps, mode=RunMode.PROGRAMMED
    ) if success else AgentResult.fail(
        "boom", steps_taken=steps, mode=RunMode.PROGRAMMED
    )
    use_case = AsyncMock()
    use_case.execute = AsyncMock(return_value=result)
    return use_case


class TestCookieRefreshSpan:
    async def test_run_refresh_emits_cookie_refresh_run_span(self, span_exporter):
        """run_refresh() must emit a cookie_refresh.run span."""
        with (
            patch("app.cookie_refresh.FileProgrammedScriptStore") as mock_store_cls,
            patch("app.cookie_refresh.VncBrowserGateway"),
            patch("app.cookie_refresh.DirectVtrackGateway"),
            patch("app.cookie_refresh.NoAgentStepsUseCase") as mock_uc_cls,
        ):
            mock_store = AsyncMock()
            mock_store.load = AsyncMock(return_value=MagicMock())
            mock_store_cls.return_value = mock_store

            mock_uc_cls.return_value = _mock_use_case(success=True, steps=5)

            await run_refresh(_make_manager())

        names = [s.name for s in span_exporter.get_finished_spans()]
        assert "cookie_refresh.run" in names, (
            f"cookie_refresh.run span not found — spans: {names}"
        )

    async def test_cookie_refresh_span_records_success(self, span_exporter):
        with (
            patch("app.cookie_refresh.FileProgrammedScriptStore") as mock_store_cls,
            patch("app.cookie_refresh.VncBrowserGateway"),
            patch("app.cookie_refresh.DirectVtrackGateway"),
            patch("app.cookie_refresh.NoAgentStepsUseCase") as mock_uc_cls,
        ):
            mock_store = AsyncMock()
            mock_store.load = AsyncMock(return_value=MagicMock())
            mock_store_cls.return_value = mock_store
            mock_uc_cls.return_value = _mock_use_case(success=True, steps=7)

            await run_refresh(_make_manager())

        span = next(
            (s for s in span_exporter.get_finished_spans() if s.name == "cookie_refresh.run"),
            None,
        )
        assert span is not None, "cookie_refresh.run span not found"
        assert span.attributes.get("refresh.success") is True

    async def test_cookie_refresh_span_records_steps_taken(self, span_exporter):
        with (
            patch("app.cookie_refresh.FileProgrammedScriptStore") as mock_store_cls,
            patch("app.cookie_refresh.VncBrowserGateway"),
            patch("app.cookie_refresh.DirectVtrackGateway"),
            patch("app.cookie_refresh.NoAgentStepsUseCase") as mock_uc_cls,
        ):
            mock_store = AsyncMock()
            mock_store.load = AsyncMock(return_value=MagicMock())
            mock_store_cls.return_value = mock_store
            mock_uc_cls.return_value = _mock_use_case(success=True, steps=12)

            await run_refresh(_make_manager())

        span = next(
            (s for s in span_exporter.get_finished_spans() if s.name == "cookie_refresh.run"),
            None,
        )
        assert span is not None, "cookie_refresh.run span not found"
        assert span.attributes.get("refresh.steps_taken") == 12

    async def test_cookie_refresh_span_records_failure(self, span_exporter):
        with (
            patch("app.cookie_refresh.FileProgrammedScriptStore") as mock_store_cls,
            patch("app.cookie_refresh.VncBrowserGateway"),
            patch("app.cookie_refresh.DirectVtrackGateway"),
            patch("app.cookie_refresh.NoAgentStepsUseCase") as mock_uc_cls,
        ):
            mock_store = AsyncMock()
            mock_store.load = AsyncMock(return_value=MagicMock())
            mock_store_cls.return_value = mock_store
            mock_uc_cls.return_value = _mock_use_case(success=False, steps=3)

            await run_refresh(_make_manager())

        span = next(
            (s for s in span_exporter.get_finished_spans() if s.name == "cookie_refresh.run"),
            None,
        )
        assert span is not None, "cookie_refresh.run span not found"
        assert span.attributes.get("refresh.success") is False
