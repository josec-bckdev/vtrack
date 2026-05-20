"""Tests for app.tracing: configure_tracing wires up the OTel TracerProvider.

OTel SDK only allows set_tracer_provider once per process (subsequent calls are
silently ignored with a warning), so tests patch app.tracing.trace.set_tracer_provider
to capture the provider argument instead of reading back global state.
"""
from unittest.mock import MagicMock, patch

from opentelemetry.sdk.trace import TracerProvider


def _run_configure(service: str = "svc", endpoint: str = "http://h:4317"):
    """Call configure_tracing with OTLP and set_tracer_provider both patched."""
    from app.tracing import configure_tracing

    captured = []
    with patch("app.tracing.OTLPSpanExporter", return_value=MagicMock()), \
         patch("app.tracing.trace.set_tracer_provider", side_effect=captured.append):
        configure_tracing(service, endpoint)
    return captured[0]


def test_configure_tracing_installs_sdk_provider():
    provider = _run_configure()
    assert isinstance(provider, TracerProvider)


def test_configure_tracing_uses_given_endpoint():
    from app.tracing import configure_tracing

    with patch("app.tracing.OTLPSpanExporter", return_value=MagicMock()) as mock_otlp, \
         patch("app.tracing.trace.set_tracer_provider"):
        configure_tracing("svc", "http://tempo:4317")
    mock_otlp.assert_called_once_with(endpoint="http://tempo:4317", insecure=True)


def test_configure_tracing_sets_service_name():
    from opentelemetry.sdk.resources import SERVICE_NAME
    provider = _run_configure(service="my-service")
    assert provider.resource.attributes.get(SERVICE_NAME) == "my-service"
