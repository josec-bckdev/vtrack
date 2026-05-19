"""Tests for Conductor orchestration logic — mocks both gateways."""
import asyncio
from datetime import time, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from conductor.conductor import Conductor, SlotConfig
from conductor.domain.ports import ContainerStats


TZ = ZoneInfo("America/Bogota")
MANAGED = ["api", "db", "redis"]

_MORNING = SlotConfig(window_open=time(5, 0), window_close=time(6, 40))
_AFTERNOON = SlotConfig(window_open=time(14, 30), window_close=time(16, 30))
SLOTS = {"morning": _MORNING, "afternoon": _AFTERNOON}


def _make_gateway(*, healthy=True, guardian=None, activate_raises=False):
    gw = AsyncMock()
    gw.health.return_value = healthy
    gw.guardian_status.return_value = guardian or {
        "morning": {"task_running": False, "current_state": "idle", "last_outcome": None, "completed_at": None},
        "afternoon": {"task_running": False, "current_state": "idle", "last_outcome": None, "completed_at": None},
    }
    if activate_raises:
        gw.activate_guardian.side_effect = Exception("already active")
    return gw


def _make_containers(*, running=False):
    cg = AsyncMock()
    cg.is_running.return_value = running
    cg.get_stats.return_value = ContainerStats(
        name="api", memory_bytes=300 * 1024 * 1024, cpu_percent=5.0
    )
    return cg


def _conductor(gateway=None, containers=None, **kwargs):
    return Conductor(
        gateway=gateway or _make_gateway(),
        containers=containers or _make_containers(),
        managed_containers=MANAGED,
        slots=SLOTS,
        **kwargs,
    )


# ── Boot sequence ─────────────────────────────────────────────────────────────

class TestBootSequence:
    async def test_outside_window_stops_running_containers(self):
        """If booted outside every window, stop any running managed containers."""
        containers = _make_containers(running=True)
        conductor = _conductor(containers=containers)

        # Freeze clock to a time clearly outside both windows (e.g. 10:00)
        frozen = datetime(2026, 5, 19, 10, 0, tzinfo=TZ)
        with patch("conductor.conductor.datetime") as mock_dt:
            mock_dt.now.return_value = frozen
            await conductor.run_boot_sequence()

        assert containers.stop.call_count == len(MANAGED)

    async def test_inside_window_starts_containers_and_activates_guardian(self):
        """If booted inside a window with guardian idle, start stack and activate."""
        containers = _make_containers(running=False)
        gateway = _make_gateway(healthy=True)
        conductor = _conductor(gateway=gateway, containers=containers)

        # 05:20 — inside morning window
        frozen = datetime(2026, 5, 19, 5, 20, tzinfo=TZ)
        with patch("conductor.conductor.datetime") as mock_dt:
            mock_dt.now.return_value = frozen
            await conductor.run_boot_sequence()

        containers.start.assert_called()
        gateway.activate_guardian.assert_called_once_with("morning")

    async def test_inside_window_guardian_already_running_skips_activate(self):
        """If guardian is already task_running, do not call activate_guardian again."""
        guardian = {
            "morning": {"task_running": True, "current_state": "watching", "last_outcome": None, "completed_at": None},
            "afternoon": {"task_running": False, "current_state": "idle", "last_outcome": None, "completed_at": None},
        }
        gateway = _make_gateway(guardian=guardian)
        conductor = _conductor(gateway=gateway)

        frozen = datetime(2026, 5, 19, 5, 20, tzinfo=TZ)
        with patch("conductor.conductor.datetime") as mock_dt:
            mock_dt.now.return_value = frozen
            await conductor.run_boot_sequence()

        gateway.activate_guardian.assert_not_called()

    async def test_inside_window_vtrack_unhealthy_still_starts_containers(self):
        """Even if health check initially fails, boot sequence still starts all containers."""
        gateway = _make_gateway(healthy=False)
        containers = _make_containers(running=False)
        conductor = _conductor(gateway=gateway, containers=containers)

        frozen = datetime(2026, 5, 19, 5, 20, tzinfo=TZ)
        with patch("conductor.conductor.datetime") as mock_dt:
            mock_dt.now.return_value = frozen
            await conductor.run_boot_sequence()

        containers.start.assert_called()


# ── _startup_slot ─────────────────────────────────────────────────────────────

class TestStartupSlot:
    async def test_starts_all_managed_containers(self):
        containers = _make_containers(running=False)
        gateway = _make_gateway()
        conductor = _conductor(gateway=gateway, containers=containers)

        await conductor._startup_slot("morning")

        assert containers.start.call_count == len(MANAGED)

    async def test_activates_guardian_after_health_ok(self):
        gateway = _make_gateway(healthy=True)
        conductor = _conductor(gateway=gateway)

        await conductor._startup_slot("morning")

        gateway.activate_guardian.assert_called_once_with("morning")

    async def test_returns_true_when_savings_above_threshold(self):
        containers = _make_containers()
        # Each container returns 300 MB → 3 × 300 = 900 MB total, above 256 MB threshold
        containers.get_stats.return_value = ContainerStats(
            name="api", memory_bytes=300 * 1024 * 1024, cpu_percent=5.0
        )
        conductor = _conductor(containers=containers, memory_threshold_mb=256.0)

        result = await conductor._startup_slot("morning")

        assert result is True

    async def test_returns_false_when_savings_below_threshold(self):
        containers = _make_containers()
        # Each container returns 10 MB → 3 × 10 = 30 MB total, below 256 MB threshold
        containers.get_stats.return_value = ContainerStats(
            name="api", memory_bytes=10 * 1024 * 1024, cpu_percent=1.0
        )
        conductor = _conductor(containers=containers, memory_threshold_mb=256.0)

        result = await conductor._startup_slot("morning")

        assert result is False

    async def test_skips_health_wait_if_already_healthy(self):
        gateway = _make_gateway(healthy=True)
        conductor = _conductor(gateway=gateway)

        # Should complete quickly — no retry loop needed
        await conductor._startup_slot("morning")

        gateway.health.assert_called()


# ── _watch_slot ───────────────────────────────────────────────────────────────

class TestWatchSlot:
    async def test_returns_when_task_running_becomes_false(self):
        """Poll until task_running is False, then return."""
        call_count = 0

        async def guardian_status_side_effect():
            nonlocal call_count
            call_count += 1
            running = call_count < 3
            return {
                "morning": {
                    "task_running": running,
                    "current_state": "watching" if running else "started",
                    "last_outcome": None if running else "started",
                    "completed_at": None,
                }
            }

        gateway = _make_gateway()
        gateway.guardian_status.side_effect = guardian_status_side_effect
        conductor = _conductor(gateway=gateway, poll_interval=0)

        await conductor._watch_slot("morning")

        assert call_count == 3

    async def test_logs_warning_on_missed_outcome(self, caplog):
        gateway = _make_gateway()
        gateway.guardian_status.return_value = {
            "morning": {
                "task_running": False,
                "current_state": "missed",
                "last_outcome": "missed",
                "completed_at": "2026-05-19T06:41:00-05:00",
            }
        }
        conductor = _conductor(gateway=gateway, poll_interval=0)

        import logging
        with caplog.at_level(logging.WARNING, logger="conductor.conductor"):
            await conductor._watch_slot("morning")

        assert any("missed" in r.message.lower() for r in caplog.records)
