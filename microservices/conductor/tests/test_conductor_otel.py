"""RED tests — conductor OTel span creation.

These tests verify that _startup_slot and _watch_slot emit the expected
OpenTelemetry spans. They fail until conductor.py is instrumented.
"""
from datetime import time
from unittest.mock import AsyncMock

import pytest
import opentelemetry.trace as trace_api
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from conductor.conductor import Conductor, SlotConfig
from conductor.domain.ports import ContainerStats


MANAGED = ["api", "db", "redis"]
SLOTS = {
    "morning": SlotConfig(window_open=time(5, 0), window_close=time(6, 40)),
    "afternoon": SlotConfig(window_open=time(14, 30), window_close=time(16, 30)),
}


def _find_span(spans, name):
    """Return first span with given name, or None."""
    return next((s for s in spans if s.name == name), None)


@pytest.fixture(autouse=True)
def span_exporter():
    # Reset OTel global singleton so each test gets a clean provider.
    trace_api._TRACER_PROVIDER = None
    trace_api._TRACER_PROVIDER_SET_ONCE._done = False

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    yield exporter
    exporter.clear()


def _make_gateway(*, healthy=True):
    gw = AsyncMock()
    gw.health.return_value = healthy
    gw.guardian_status.return_value = {
        "morning": {"task_running": False, "current_state": "idle", "last_outcome": "started", "completed_at": None},
        "afternoon": {"task_running": False, "current_state": "idle", "last_outcome": None, "completed_at": None},
    }
    return gw


def _make_containers():
    cg = AsyncMock()
    cg.is_running.return_value = False
    cg.get_stats.return_value = ContainerStats(
        name="api", memory_bytes=300 * 1024 * 1024, cpu_percent=5.0
    )
    return cg


def _conductor(**kwargs):
    kwargs.setdefault("health_timeout", 0)
    kwargs.setdefault("health_poll_interval", 0)
    return Conductor(
        gateway=kwargs.pop("gateway", _make_gateway()),
        containers=kwargs.pop("containers", _make_containers()),
        managed_containers=MANAGED,
        slots=SLOTS,
        **kwargs,
    )


class TestStartupSlotSpans:
    async def test_startup_slot_emits_container_start_span(self, span_exporter):
        await _conductor()._startup_slot("morning")
        names = [s.name for s in span_exporter.get_finished_spans()]
        assert "conductor.container.start" in names

    async def test_container_start_span_has_count_attribute(self, span_exporter):
        await _conductor()._startup_slot("morning")
        span = _find_span(span_exporter.get_finished_spans(), "conductor.container.start")
        assert span is not None, "conductor.container.start span not found"
        assert span.attributes["containers.count"] == len(MANAGED)

    async def test_startup_slot_emits_health_wait_span(self, span_exporter):
        await _conductor()._startup_slot("morning")
        names = [s.name for s in span_exporter.get_finished_spans()]
        assert "conductor.health.wait" in names

    async def test_startup_slot_emits_guardian_activate_span(self, span_exporter):
        await _conductor()._startup_slot("morning")
        names = [s.name for s in span_exporter.get_finished_spans()]
        assert "conductor.guardian.activate" in names

    async def test_guardian_activate_span_has_slot_name(self, span_exporter):
        await _conductor()._startup_slot("morning")
        span = _find_span(span_exporter.get_finished_spans(), "conductor.guardian.activate")
        assert span is not None, "conductor.guardian.activate span not found"
        assert span.attributes["slot.name"] == "morning"

    async def test_startup_slot_emits_resource_eval_span(self, span_exporter):
        await _conductor()._startup_slot("morning")
        names = [s.name for s in span_exporter.get_finished_spans()]
        assert "conductor.resource.eval" in names

    async def test_resource_eval_span_has_memory_and_cpu_attributes(self, span_exporter):
        await _conductor()._startup_slot("morning")
        span = _find_span(span_exporter.get_finished_spans(), "conductor.resource.eval")
        assert span is not None, "conductor.resource.eval span not found"
        assert "resource.total_memory_mb" in span.attributes
        assert "resource.total_cpu_percent" in span.attributes
        assert "resource.decision" in span.attributes

    async def test_resource_eval_decision_is_stop_when_above_threshold(self, span_exporter):
        containers = _make_containers()
        # 3 containers × 300 MB = 900 MB → above 256 MB → decision: stop
        containers.get_stats.return_value = ContainerStats(
            name="api", memory_bytes=300 * 1024 * 1024, cpu_percent=5.0
        )
        await _conductor(containers=containers, memory_threshold_mb=256.0)._startup_slot("morning")
        span = _find_span(span_exporter.get_finished_spans(), "conductor.resource.eval")
        assert span is not None, "conductor.resource.eval span not found"
        assert span.attributes["resource.decision"] == "stop"

    async def test_resource_eval_decision_is_keep_when_below_threshold(self, span_exporter):
        containers = _make_containers()
        # 3 containers × 10 MB = 30 MB → below 256 MB → decision: keep
        containers.get_stats.return_value = ContainerStats(
            name="api", memory_bytes=10 * 1024 * 1024, cpu_percent=1.0
        )
        await _conductor(containers=containers, memory_threshold_mb=256.0)._startup_slot("morning")
        span = _find_span(span_exporter.get_finished_spans(), "conductor.resource.eval")
        assert span is not None, "conductor.resource.eval span not found"
        assert span.attributes["resource.decision"] == "keep"


class TestWatchSlotSpans:
    async def test_watch_slot_emits_slot_watch_span(self, span_exporter):
        gateway = _make_gateway()
        gateway.guardian_status.return_value = {
            "morning": {
                "task_running": False,
                "current_state": "started",
                "last_outcome": "started",
                "completed_at": None,
            }
        }
        await _conductor(gateway=gateway, poll_interval=0)._watch_slot("morning")
        names = [s.name for s in span_exporter.get_finished_spans()]
        assert "conductor.slot.watch" in names

    async def test_slot_watch_span_records_outcome(self, span_exporter):
        gateway = _make_gateway()
        gateway.guardian_status.return_value = {
            "morning": {
                "task_running": False,
                "current_state": "started",
                "last_outcome": "started",
                "completed_at": None,
            }
        }
        await _conductor(gateway=gateway, poll_interval=0)._watch_slot("morning")
        span = _find_span(span_exporter.get_finished_spans(), "conductor.slot.watch")
        assert span is not None, "conductor.slot.watch span not found"
        assert span.attributes["slot.outcome"] == "started"

    async def test_slot_watch_span_records_missed_outcome(self, span_exporter):
        gateway = _make_gateway()
        gateway.guardian_status.return_value = {
            "morning": {
                "task_running": False,
                "current_state": "missed",
                "last_outcome": "missed",
                "completed_at": None,
            }
        }
        await _conductor(gateway=gateway, poll_interval=0)._watch_slot("morning")
        span = _find_span(span_exporter.get_finished_spans(), "conductor.slot.watch")
        assert span is not None, "conductor.slot.watch span not found"
        assert span.attributes["slot.outcome"] == "missed"
