from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ContainerStats:
    name: str
    memory_bytes: int
    cpu_percent: float


class IVtrackGateway(ABC):
    @abstractmethod
    async def health(self) -> bool: ...

    @abstractmethod
    async def guardian_status(self) -> dict: ...

    @abstractmethod
    async def activate_guardian(self, slot: str) -> None: ...

    @abstractmethod
    async def collection_status(self) -> dict: ...


class IContainerGateway(ABC):
    @abstractmethod
    async def start(self, name: str) -> None: ...

    @abstractmethod
    async def stop(self, name: str) -> None: ...

    @abstractmethod
    async def is_running(self, name: str) -> bool: ...

    @abstractmethod
    async def get_stats(self, name: str) -> ContainerStats: ...
