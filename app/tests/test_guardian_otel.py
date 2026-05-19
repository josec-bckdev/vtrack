"""RED tests — guardian OTel child spans.

Verify that _watch_slot emits:
  - guardian.slot.{name}      root span wrapping the entire watch
  - guardian.watching         sub-span while polling
  - guardian.collection.start sub-span when collection fires

Fail until app/scheduler.py is instrumented with opentelemetry-api spans.
"""
import pytest
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import AsyncMock, MagicMock, patch

import opentelemetry.trace as trace_api
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.config import JobSlot
from app.scheduler import Scheduler, GuardianState


TZ = ZoneInfo("America/Bogota")


def _dt(h: int, m: int, s: int = 0) -> datetime:
    return datetime(2026, 5, 20, h, m, s, tzinfo=TZ)


def _make_slot(
    window_open: time,
    fire_time: time,
    grace: int,
    window_close: time,
) -> JobSlot:
    return JobSlot(
        window_open=window_open,
        fire_time=fire_time,
        grace_minutes=grace,
        window_close=window_close,
    )


def _make_adapter(*, running: bool = False):
    adapter = MagicMock()
    adapter.is_running.return_value = running
    adapter.start = AsyncMock()
    return adapter


@pytest.fixture(scope="session")
def _guardian_provider():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace_api._TRACER_PROVIDER = None
    trace_api._TRACER_PROVIDER_SET_ONCE._done = False
    trace.set_tracer_provider(provider)
    return exporter


@pytest.fixture(autouse=True)
def span_exporter(_guardian_provider):
    _guardian_provider.clear()
    yield _guardian_provider


def _freeze(frozen: datetime):
    mock = MagicMock(wraps=datetime)
    mock.now.return_value = frozen
    mock.combine = datetime.combine
    return patch("app.scheduler.datetime", mock)


class TestGuardianSlotSpan:
    async def test_watch_slot_emits_guardian_slot_span(self, span_exporter):
        """_watch_slot must emit a guardian.slot.morning (or .afternoon) span."""
        slot = _make_slot(
            window_open=time(5, 0),
            fire_time=time(5, 30),
            grace=10,
            window_close=time(6, 40),
        )
        adapter = _make_adapter(running=True)
        scheduler = Scheduler()

        with _freeze(_dt(5, 20)):
            await scheduler._watch_slot(slot, adapter, slot_name="morning")

        names = [s.name for s in span_exporter.get_finished_spans()]
        assert any("guardian.slot" in n for n in names), (
            f"No guardian.slot span found — spans emitted: {names}"
        )

    async def test_guardian_slot_span_has_slot_name_attribute(self, span_exporter):
        slot = _make_slot(
            window_open=time(5, 0),
            fire_time=time(5, 30),
            grace=10,
            window_close=time(6, 40),
        )
        adapter = _make_adapter(running=True)
        scheduler = Scheduler()

        with _freeze(_dt(5, 20)):
            await scheduler._watch_slot(slot, adapter, slot_name="morning")

        span = next(
            (s for s in span_exporter.get_finished_spans() if "guardian.slot" in s.name),
            None,
        )
        assert span is not None, "guardian.slot span not found"
        assert span.attributes.get("slot.name") == "morning"


class TestGuardianWatchingSpan:
    async def test_watch_slot_emits_guardian_watching_span(self, span_exporter):
        """When the guardian enters the WATCHING state it must emit a guardian.watching span."""
        slot = _make_slot(
            window_open=time(5, 0),
            fire_time=time(5, 30),
            grace=10,
            window_close=time(6, 40),
        )
        adapter = _make_adapter(running=True)
        scheduler = Scheduler()

        with _freeze(_dt(5, 20)):
            await scheduler._watch_slot(slot, adapter, slot_name="morning")

        names = [s.name for s in span_exporter.get_finished_spans()]
        assert "guardian.watching" in names, (
            f"guardian.watching span not found — spans: {names}"
        )


class TestGuardianCollectionStartSpan:
    async def test_watch_slot_emits_collection_start_span_when_already_running(self, span_exporter):
        """When collection is already running, guardian must emit guardian.collection.start
        with trigger=already_running."""
        slot = _make_slot(
            window_open=time(5, 0),
            fire_time=time(5, 30),
            grace=10,
            window_close=time(6, 40),
        )
        adapter = _make_adapter(running=True)
        scheduler = Scheduler()

        with _freeze(_dt(5, 20)):
            await scheduler._watch_slot(slot, adapter, slot_name="morning")

        span = next(
            (s for s in span_exporter.get_finished_spans() if s.name == "guardian.collection.start"),
            None,
        )
        assert span is not None, "guardian.collection.start span not found"
        assert span.attributes.get("trigger") == "already_running"

    async def test_watch_slot_emits_collection_start_span_when_grace_exceeded(self, span_exporter):
        """When grace period is exceeded, guardian must emit guardian.collection.start
        with trigger=grace_exceeded."""
        slot = _make_slot(
            window_open=time(5, 0),
            fire_time=time(5, 30),
            grace=10,
            window_close=time(6, 40),
        )
        adapter = _make_adapter(running=False)
        scheduler = Scheduler()

        # Past fire_time + grace — guardian will call adapter.start()
        with _freeze(_dt(5, 45)):
            await scheduler._watch_slot(slot, adapter, slot_name="morning")

        span = next(
            (s for s in span_exporter.get_finished_spans() if s.name == "guardian.collection.start"),
            None,
        )
        assert span is not None, "guardian.collection.start span not found"
        assert span.attributes.get("trigger") == "grace_exceeded"
