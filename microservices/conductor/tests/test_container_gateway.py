"""Failing tests for DockerContainerGateway — mocks docker SDK, no daemon needed."""
import pytest
import docker.errors
from unittest.mock import MagicMock, patch, AsyncMock

from conductor.adapters.container_gateway import DockerContainerGateway
from conductor.domain.ports import ContainerStats


@pytest.fixture
def gateway():
    return DockerContainerGateway()


def _mock_container(status: str = "running") -> MagicMock:
    container = MagicMock()
    container.status = status
    container.reload = MagicMock()
    return container


def _cpu_stats(total: int, system: int, online_cpus: int = 2) -> dict:
    return {
        "cpu_stats": {
            "cpu_usage": {"total_usage": total},
            "system_cpu_usage": system,
            "online_cpus": online_cpus,
        },
        "precpu_stats": {
            "cpu_usage": {"total_usage": total - 1_000_000},
            "system_cpu_usage": system - 100_000_000,
        },
        "memory_stats": {"usage": 104_857_600},  # 100 MB
    }


class TestIsRunning:
    async def test_returns_true_when_running(self, gateway):
        container = _mock_container("running")
        with patch("conductor.adapters.container_gateway.docker") as mock_docker:
            mock_docker.from_env.return_value.containers.get.return_value = container
            result = await gateway.is_running("api")
        assert result is True

    async def test_returns_false_when_exited(self, gateway):
        container = _mock_container("exited")
        with patch("conductor.adapters.container_gateway.docker") as mock_docker:
            mock_docker.from_env.return_value.containers.get.return_value = container
            result = await gateway.is_running("api")
        assert result is False

    async def test_returns_false_when_container_not_found(self, gateway):
        with patch("conductor.adapters.container_gateway.docker") as mock_docker:
            mock_docker.from_env.return_value.containers.get.side_effect = Exception("not found")
            mock_docker.errors.NotFound = Exception
            result = await gateway.is_running("api")
        assert result is False


class TestStart:
    async def test_calls_start_on_container(self, gateway):
        container = _mock_container("exited")
        with patch("conductor.adapters.container_gateway.docker") as mock_docker:
            mock_docker.from_env.return_value.containers.get.return_value = container
            await gateway.start("api")
        container.start.assert_called_once()

    async def test_skips_start_when_already_running(self, gateway):
        container = _mock_container("running")
        with patch("conductor.adapters.container_gateway.docker") as mock_docker:
            mock_docker.from_env.return_value.containers.get.return_value = container
            await gateway.start("api")
        container.start.assert_not_called()

    async def test_skips_start_when_container_not_found(self, gateway):
        with patch("conductor.adapters.container_gateway.docker") as mock_docker:
            mock_docker.errors.NotFound = docker.errors.NotFound
            mock_docker.from_env.return_value.containers.get.side_effect = docker.errors.NotFound("alert_processor")
            await gateway.start("alert_processor")  # must not raise


class TestStop:
    async def test_calls_stop_on_container(self, gateway):
        container = _mock_container("running")
        with patch("conductor.adapters.container_gateway.docker") as mock_docker:
            mock_docker.from_env.return_value.containers.get.return_value = container
            await gateway.stop("api")
        container.stop.assert_called_once()

    async def test_skips_stop_when_already_stopped(self, gateway):
        container = _mock_container("exited")
        with patch("conductor.adapters.container_gateway.docker") as mock_docker:
            mock_docker.from_env.return_value.containers.get.return_value = container
            await gateway.stop("api")
        container.stop.assert_not_called()

    async def test_skips_stop_when_container_not_found(self, gateway):
        with patch("conductor.adapters.container_gateway.docker") as mock_docker:
            mock_docker.errors.NotFound = docker.errors.NotFound
            mock_docker.from_env.return_value.containers.get.side_effect = docker.errors.NotFound("alert_processor")
            await gateway.stop("alert_processor")  # must not raise


class TestGetStats:
    async def test_returns_container_stats(self, gateway):
        container = _mock_container("running")
        raw = _cpu_stats(total=10_000_000, system=1_000_000_000)
        container.stats.return_value = raw

        with patch("conductor.adapters.container_gateway.docker") as mock_docker:
            mock_docker.from_env.return_value.containers.get.return_value = container
            result = await gateway.get_stats("api")

        assert isinstance(result, ContainerStats)
        assert result.name == "api"
        assert result.memory_bytes == 104_857_600

    async def test_cpu_percent_is_non_negative(self, gateway):
        container = _mock_container("running")
        raw = _cpu_stats(total=10_000_000, system=1_000_000_000)
        container.stats.return_value = raw

        with patch("conductor.adapters.container_gateway.docker") as mock_docker:
            mock_docker.from_env.return_value.containers.get.return_value = container
            result = await gateway.get_stats("api")

        assert result.cpu_percent >= 0.0
