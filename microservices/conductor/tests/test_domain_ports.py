"""Failing tests for domain ports: IVtrackGateway, IContainerGateway, ContainerStats."""
import pytest
from abc import ABC

from conductor.domain.ports import (
    ContainerStats,
    IVtrackGateway,
    IContainerGateway,
)


class TestContainerStats:
    def test_is_frozen_dataclass(self):
        stats = ContainerStats(name="api", memory_bytes=104857600, cpu_percent=12.5)
        assert stats.name == "api"
        assert stats.memory_bytes == 104857600
        assert stats.cpu_percent == 12.5

    def test_immutable(self):
        stats = ContainerStats(name="api", memory_bytes=1024, cpu_percent=1.0)
        with pytest.raises((AttributeError, TypeError)):
            stats.name = "other"  # type: ignore[misc]


class TestIVtrackGateway:
    def test_is_abstract(self):
        assert issubclass(IVtrackGateway, ABC)

    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            IVtrackGateway()  # type: ignore[abstract]

    def test_concrete_subclass_must_implement_all_methods(self):
        class Incomplete(IVtrackGateway):
            pass

        with pytest.raises(TypeError):
            Incomplete()

    def test_concrete_subclass_is_instantiable(self):
        class Concrete(IVtrackGateway):
            async def health(self) -> bool:
                return True

            async def guardian_status(self) -> dict:
                return {}

            async def activate_guardian(self, slot: str) -> None:
                pass

            async def collection_status(self) -> dict:
                return {}

        obj = Concrete()
        assert isinstance(obj, IVtrackGateway)


class TestIContainerGateway:
    def test_is_abstract(self):
        assert issubclass(IContainerGateway, ABC)

    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            IContainerGateway()  # type: ignore[abstract]

    def test_concrete_subclass_must_implement_all_methods(self):
        class Incomplete(IContainerGateway):
            pass

        with pytest.raises(TypeError):
            Incomplete()

    def test_concrete_subclass_is_instantiable(self):
        class Concrete(IContainerGateway):
            async def start(self, name: str) -> None:
                pass

            async def stop(self, name: str) -> None:
                pass

            async def is_running(self, name: str) -> bool:
                return False

            async def get_stats(self, name: str) -> ContainerStats:
                return ContainerStats(name=name, memory_bytes=0, cpu_percent=0.0)

        obj = Concrete()
        assert isinstance(obj, IContainerGateway)
