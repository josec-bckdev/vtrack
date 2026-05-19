"""RED tests — collection.run OTel span.

Verifies that start() opens a collection.run span and stop() closes it with
datapoints and duration_s attributes.

Fails until app/scraper_async.py is instrumented.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import opentelemetry.trace as trace_api
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.adapters.collection_state import InMemoryCollectionState
from app.domain.ports import IRouteDataRepository
from app.scraper_async import AsyncCollectionManager


def _make_manager() -> AsyncCollectionManager:
    mock_repo = MagicMock(spec=IRouteDataRepository)
    mock_repo.create_task.return_value = 42
    return AsyncCollectionManager(
        repository=mock_repo,
        state_store=InMemoryCollectionState(),
    )


@pytest.fixture(scope="session")
def _collection_provider():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace_api._TRACER_PROVIDER = None
    trace_api._TRACER_PROVIDER_SET_ONCE._done = False
    trace.set_tracer_provider(provider)
    return exporter


@pytest.fixture(autouse=True)
def span_exporter(_collection_provider):
    _collection_provider.clear()
    yield _collection_provider


class TestCollectionRunSpan:
    async def test_start_and_stop_emits_collection_run_span(self, span_exporter):
        """start() + stop() must produce a finished collection.run span."""
        manager = _make_manager()
        with patch.object(manager, "_collection_loop", AsyncMock()):
            await manager.start()
            await manager.stop()

        names = [s.name for s in span_exporter.get_finished_spans()]
        assert "collection.run" in names, (
            f"collection.run span not found — spans: {names}"
        )

    async def test_collection_run_span_has_task_id(self, span_exporter):
        """collection.run span must carry collection.task_id so traces can be
        correlated with the DB task record."""
        manager = _make_manager()
        with patch.object(manager, "_collection_loop", AsyncMock()):
            await manager.start()
            await manager.stop()

        span = next(
            (s for s in span_exporter.get_finished_spans() if s.name == "collection.run"),
            None,
        )
        assert span is not None, "collection.run span not found"
        assert span.attributes.get("collection.task_id") == 42

    async def test_collection_run_span_has_datapoints_attribute(self, span_exporter):
        """collection.run span must record the final datapoints count."""
        manager = _make_manager()
        with patch.object(manager, "_collection_loop", AsyncMock()):
            await manager.start()
            # Simulate 3 datapoints collected
            manager._state.increment_datapoints()
            manager._state.increment_datapoints()
            manager._state.increment_datapoints()
            await manager.stop()

        span = next(
            (s for s in span_exporter.get_finished_spans() if s.name == "collection.run"),
            None,
        )
        assert span is not None, "collection.run span not found"
        assert span.attributes.get("collection.datapoints") == 3

    async def test_collection_run_span_has_duration_attribute(self, span_exporter):
        """collection.run span must record wall-clock duration in seconds."""
        manager = _make_manager()
        with patch.object(manager, "_collection_loop", AsyncMock()):
            await manager.start()
            await manager.stop()

        span = next(
            (s for s in span_exporter.get_finished_spans() if s.name == "collection.run"),
            None,
        )
        assert span is not None, "collection.run span not found"
        assert "collection.duration_s" in span.attributes
