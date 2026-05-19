"""RED tests — trace context propagation from conductor to vtrack.

These tests verify that HttpxVtrackGateway accepts a transport parameter so the
caller can wrap it with AsyncOpenTelemetryTransport to inject W3C traceparent
headers into outgoing requests.

Fails until HttpxVtrackGateway.__init__ accepts a `transport` keyword argument.
"""
import httpx
import pytest
from opentelemetry import trace
from opentelemetry.instrumentation.httpx import AsyncOpenTelemetryTransport
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
import opentelemetry.trace as trace_api

from conductor.adapters.vtrack_gateway import HttpxVtrackGateway


@pytest.fixture(scope="session")
def _propagation_provider():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace_api._TRACER_PROVIDER = None
    trace_api._TRACER_PROVIDER_SET_ONCE._done = False
    trace.set_tracer_provider(provider)
    return exporter


@pytest.fixture(autouse=True)
def clean_exporter(_propagation_provider):
    _propagation_provider.clear()
    yield _propagation_provider


class CapturingTransport(httpx.AsyncBaseTransport):
    """Records outgoing request headers without making network calls."""

    def __init__(self):
        self.last_headers: dict = {}

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.last_headers = dict(request.headers)
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            content=b"{}",
        )


class TestTraceparentInjection:
    async def test_activate_guardian_accepts_otel_transport(self):
        """Gateway must accept a transport parameter so the infrastructure layer
        can inject AsyncOpenTelemetryTransport for W3C trace propagation."""
        capturing = CapturingTransport()
        otel_transport = AsyncOpenTelemetryTransport(capturing)
        # Fails if HttpxVtrackGateway does not accept transport=
        gateway = HttpxVtrackGateway("http://api:8000", transport=otel_transport)
        assert gateway is not None

    async def test_activate_guardian_injects_traceparent_within_active_span(self):
        """Within an active span, activate_guardian must send the W3C traceparent
        header so vtrack can continue the distributed trace."""
        capturing = CapturingTransport()
        otel_transport = AsyncOpenTelemetryTransport(capturing)
        gateway = HttpxVtrackGateway("http://api:8000", transport=otel_transport)

        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("conductor.slot"):
            await gateway.activate_guardian("morning")

        assert "traceparent" in capturing.last_headers, (
            f"traceparent header missing — headers sent: {list(capturing.last_headers)}"
        )

    async def test_health_uses_otel_transport(self):
        """health() must also use the configured transport."""
        capturing = CapturingTransport()
        otel_transport = AsyncOpenTelemetryTransport(capturing)
        gateway = HttpxVtrackGateway("http://api:8000", transport=otel_transport)

        with trace.get_tracer("test").start_as_current_span("conductor.health.check"):
            await gateway.health()

        assert "traceparent" in capturing.last_headers
