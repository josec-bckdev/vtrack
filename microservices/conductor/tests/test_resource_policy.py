"""Failing tests for resource policy pure functions."""
import pytest

from conductor.domain.ports import ContainerStats
from conductor.domain.resource_policy import (
    ResourceSummary,
    evaluate_savings,
    should_stop_after_slot,
)

_100MB = 100 * 1024 * 1024
_200MB = 200 * 1024 * 1024
_300MB = 300 * 1024 * 1024


class TestEvaluateSavings:
    def test_sums_memory_bytes_to_mb(self):
        stats = [
            ContainerStats(name="api", memory_bytes=_100MB, cpu_percent=5.0),
            ContainerStats(name="db", memory_bytes=_200MB, cpu_percent=3.0),
        ]
        summary = evaluate_savings(stats)
        assert summary.total_memory_mb == pytest.approx(300.0)

    def test_sums_cpu_percent(self):
        stats = [
            ContainerStats(name="api", memory_bytes=_100MB, cpu_percent=5.0),
            ContainerStats(name="db", memory_bytes=_100MB, cpu_percent=3.0),
        ]
        summary = evaluate_savings(stats)
        assert summary.total_cpu_percent == pytest.approx(8.0)

    def test_preserves_container_list(self):
        stats = [
            ContainerStats(name="api", memory_bytes=_100MB, cpu_percent=1.0),
        ]
        summary = evaluate_savings(stats)
        assert summary.containers == stats

    def test_empty_list_returns_zero_totals(self):
        summary = evaluate_savings([])
        assert summary.total_memory_mb == 0.0
        assert summary.total_cpu_percent == 0.0

    def test_returns_resource_summary(self):
        summary = evaluate_savings([])
        assert isinstance(summary, ResourceSummary)


class TestShouldStopAfterSlot:
    def test_stops_when_memory_above_threshold(self):
        summary = ResourceSummary(
            containers=[],
            total_memory_mb=512.0,
            total_cpu_percent=10.0,
        )
        assert should_stop_after_slot(summary, memory_threshold_mb=256.0) is True

    def test_stops_when_memory_equals_threshold(self):
        summary = ResourceSummary(
            containers=[],
            total_memory_mb=256.0,
            total_cpu_percent=5.0,
        )
        assert should_stop_after_slot(summary, memory_threshold_mb=256.0) is True

    def test_keeps_running_when_memory_below_threshold(self):
        summary = ResourceSummary(
            containers=[],
            total_memory_mb=100.0,
            total_cpu_percent=2.0,
        )
        assert should_stop_after_slot(summary, memory_threshold_mb=256.0) is False

    def test_default_threshold_is_256mb(self):
        above = ResourceSummary(containers=[], total_memory_mb=300.0, total_cpu_percent=0.0)
        below = ResourceSummary(containers=[], total_memory_mb=100.0, total_cpu_percent=0.0)
        assert should_stop_after_slot(above) is True
        assert should_stop_after_slot(below) is False
