"""FileProgrammedScriptStore — read-only loader for programmed_steps.json."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from app.cookie_refresh.domain.entities import ProgrammedScript, ProgrammedStep
from app.cookie_refresh.domain.ports import IProgrammedScriptStore


class FileProgrammedScriptStore(IProgrammedScriptStore):
    def __init__(self, path: str) -> None:
        self._path = path

    async def load(self) -> Optional[ProgrammedScript]:
        p = Path(self._path)
        if not p.exists():
            return None
        data = json.loads(p.read_text())
        steps = [
            ProgrammedStep(
                action_type=s["action_type"],
                params=s["params"],
                delay_after_ms=s.get("delay_after_ms", 0.0),
            )
            for s in data["steps"]
        ]
        return ProgrammedScript(steps=steps)
