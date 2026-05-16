"""Unit tests for run_refresh() — the cookie_refresh public entry point."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


async def _run(collection_manager=None):
    from app.cookie_refresh import run_refresh
    return await run_refresh(collection_manager or MagicMock())


def _mock_store(script):
    store = MagicMock()
    store.load = AsyncMock(return_value=script)
    return store


def _mock_use_case(success: bool, steps: int = 3, error: str = ""):
    result = MagicMock()
    result.success = success
    result.steps_taken = steps
    result.error = error
    use_case = MagicMock()
    use_case.execute = AsyncMock(return_value=result)
    return use_case


@pytest.mark.asyncio
class TestRunRefresh:
    async def test_returns_true_on_success(self):
        script = MagicMock()
        with patch("app.cookie_refresh.FileProgrammedScriptStore", return_value=_mock_store(script)), \
             patch("app.cookie_refresh.VncBrowserGateway"), \
             patch("app.cookie_refresh.DirectVtrackGateway"), \
             patch("app.cookie_refresh.NoAgentStepsUseCase", return_value=_mock_use_case(True)):
            result = await _run()
        assert result is True

    async def test_returns_false_when_script_not_found(self):
        with patch("app.cookie_refresh.FileProgrammedScriptStore", return_value=_mock_store(None)):
            result = await _run()
        assert result is False

    async def test_returns_false_when_use_case_fails(self):
        script = MagicMock()
        with patch("app.cookie_refresh.FileProgrammedScriptStore", return_value=_mock_store(script)), \
             patch("app.cookie_refresh.VncBrowserGateway"), \
             patch("app.cookie_refresh.DirectVtrackGateway"), \
             patch("app.cookie_refresh.NoAgentStepsUseCase",
                   return_value=_mock_use_case(False, steps=2, error="timeout")):
            result = await _run()
        assert result is False

    async def test_passes_collection_manager_to_direct_vtrack_gateway(self):
        script = MagicMock()
        cm = MagicMock()
        captured = {}

        def capture_vtrack(manager):
            captured["manager"] = manager
            return MagicMock()

        with patch("app.cookie_refresh.FileProgrammedScriptStore", return_value=_mock_store(script)), \
             patch("app.cookie_refresh.VncBrowserGateway"), \
             patch("app.cookie_refresh.DirectVtrackGateway", side_effect=capture_vtrack), \
             patch("app.cookie_refresh.NoAgentStepsUseCase", return_value=_mock_use_case(True)):
            await _run(cm)

        assert captured["manager"] is cm
