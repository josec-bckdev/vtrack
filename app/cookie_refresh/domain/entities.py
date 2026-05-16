"""Pure domain entities — no framework imports, no I/O."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class RunMode(str, Enum):
    PROGRAMMED = "programmed"


class FailureReason(str, Enum):
    NO_COOKIES = "no_cookies"
    VTRACK_POST_FAILED = "vtrack_post_failed"
    EXCEPTION = "exception"


@dataclass(frozen=True)
class SessionCookies:
    cf_clearance: str
    ci_session: str

    def __post_init__(self) -> None:
        if not self.cf_clearance or not self.cf_clearance.strip():
            raise ValueError("cf_clearance cannot be empty")
        if not self.ci_session or not self.ci_session.strip():
            raise ValueError("ci_session cannot be empty")


@dataclass
class AgentResult:
    success: bool
    cookies: Optional[SessionCookies]
    error: Optional[str]
    steps_taken: int
    mode: Optional[RunMode] = None
    failure_reason: Optional[FailureReason] = None

    @classmethod
    def ok(cls, cookies: SessionCookies, steps_taken: int, mode: Optional[RunMode] = None) -> "AgentResult":
        if cookies is None:
            raise ValueError("cookies required for a success result")
        return cls(success=True, cookies=cookies, error=None, steps_taken=steps_taken, mode=mode)

    @classmethod
    def fail(cls, error: str, steps_taken: int, mode: Optional[RunMode] = None,
             failure_reason: Optional[FailureReason] = None) -> "AgentResult":
        if not error:
            raise ValueError("error message required for a failure result")
        return cls(success=False, cookies=None, error=error, steps_taken=steps_taken,
                   mode=mode, failure_reason=failure_reason)


@dataclass(frozen=True)
class ProgrammedStep:
    action_type: str
    params: dict
    delay_after_ms: float = 0.0


@dataclass(frozen=True)
class ProgrammedScript:
    steps: list[ProgrammedStep]
