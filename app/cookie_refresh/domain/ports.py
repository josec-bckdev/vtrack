"""Abstract ports (interfaces) — define the shape of every external dependency."""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional

from app.cookie_refresh.domain.entities import ProgrammedScript, SessionCookies


class IBrowserGateway(ABC):
    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def navigate(self, url: str, wait_seconds: float = 6.0) -> None: ...

    @abstractmethod
    async def take_screenshot(self) -> bytes: ...

    @abstractmethod
    async def click(self, x: int, y: int) -> None: ...

    @abstractmethod
    async def double_click(self, x: int, y: int) -> None: ...

    @abstractmethod
    async def triple_click(self, x: int, y: int) -> None: ...

    @abstractmethod
    async def type_text(self, text: str) -> None: ...

    @abstractmethod
    async def press_key(self, key: str) -> None: ...

    @abstractmethod
    async def scroll(self, x: int, y: int, direction: str, amount: int) -> None: ...

    @abstractmethod
    async def right_click(self, x: int, y: int) -> None: ...

    @abstractmethod
    async def left_click_drag(self, start_x: int, start_y: int, end_x: int, end_y: int) -> None: ...

    @abstractmethod
    async def close(self) -> None: ...

    @abstractmethod
    async def get_cookies(self, names: list[str]) -> SessionCookies: ...


class IVtrackGateway(ABC):
    @abstractmethod
    async def post_cookies(self, cookies: SessionCookies) -> bool: ...


class IProgrammedScriptStore(ABC):
    @abstractmethod
    async def load(self) -> Optional[ProgrammedScript]: ...
