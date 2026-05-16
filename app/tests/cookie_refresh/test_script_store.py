"""Unit tests for FileProgrammedScriptStore."""
import json
import pytest
from pathlib import Path

from app.cookie_refresh.adapters.script_store import FileProgrammedScriptStore
from app.cookie_refresh.domain.entities import ProgrammedScript


@pytest.mark.asyncio
class TestFileProgrammedScriptStore:
    async def test_load_returns_none_when_file_missing(self, tmp_path):
        store = FileProgrammedScriptStore(str(tmp_path / "missing.json"))
        result = await store.load()
        assert result is None

    async def test_load_returns_script_with_correct_steps(self, tmp_path):
        data = {
            "steps": [
                {"action_type": "left_click", "params": {"coordinate": [100, 200]}, "delay_after_ms": 500.0},
                {"action_type": "get_cookies", "params": {"names": ["cf_clearance", "ci_session"]}},
            ]
        }
        path = tmp_path / "steps.json"
        path.write_text(json.dumps(data))

        store = FileProgrammedScriptStore(str(path))
        result = await store.load()

        assert isinstance(result, ProgrammedScript)
        assert len(result.steps) == 2
        assert result.steps[0].action_type == "left_click"
        assert result.steps[0].delay_after_ms == 500.0
        assert result.steps[1].action_type == "get_cookies"

    async def test_step_delay_defaults_to_zero(self, tmp_path):
        data = {"steps": [{"action_type": "left_click", "params": {"coordinate": [0, 0]}}]}
        path = tmp_path / "steps.json"
        path.write_text(json.dumps(data))

        store = FileProgrammedScriptStore(str(path))
        result = await store.load()

        assert result is not None
        assert result.steps[0].delay_after_ms == 0.0
