"""RED tests — notification-sender OTel spans.

Verifies that _process_alert_queue emits:
  - notification_sender.alert.send  {alert.ruta, alert.type,
                                     notification.provider, notification.success}

Fails until microservices/notification-sender/main.py is instrumented.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parents[3] / "shared-package" / "src"))

import pytest
from unittest.mock import MagicMock

import opentelemetry.trace as trace_api
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from main import NotificationConsumer


@pytest.fixture(scope="session")
def _notif_provider():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace_api._TRACER_PROVIDER = None
    trace_api._TRACER_PROVIDER_SET_ONCE._done = False
    trace.set_tracer_provider(provider)
    return exporter


@pytest.fixture(autouse=True)
def span_exporter(_notif_provider):
    _notif_provider.clear()
    yield _notif_provider


def _make_consumer() -> NotificationConsumer:
    consumer = NotificationConsumer.__new__(NotificationConsumer)
    consumer.redis_queue = MagicMock()
    consumer.telegram = MagicMock()
    consumer.running = True
    consumer.processed = 0
    return consumer


_ALERT = {
    "ruta": 9,
    "alert_type": "GEOFENCE_ENTRY",
    "area_name": "North Terminal",
    "severity": "WARNING",
    "latitude": 4.71,
    "longitude": -74.07,
}


class TestAlertSendSpan:
    def test_process_alert_emits_send_span(self, span_exporter):
        consumer = _make_consumer()
        consumer.redis_queue.pop_alert.return_value = dict(_ALERT)
        consumer.telegram.send_alert.return_value = True

        consumer._process_alert_queue()

        names = [s.name for s in span_exporter.get_finished_spans()]
        assert "notification_sender.alert.send" in names, (
            f"notification_sender.alert.send span not found — spans: {names}"
        )

    def test_send_span_has_ruta_and_type(self, span_exporter):
        consumer = _make_consumer()
        consumer.redis_queue.pop_alert.return_value = dict(_ALERT)
        consumer.telegram.send_alert.return_value = True

        consumer._process_alert_queue()

        span = next(
            (s for s in span_exporter.get_finished_spans()
             if s.name == "notification_sender.alert.send"),
            None,
        )
        assert span is not None, "notification_sender.alert.send span not found"
        assert span.attributes.get("alert.ruta") == 9
        assert span.attributes.get("alert.type") == "GEOFENCE_ENTRY"

    def test_send_span_has_provider(self, span_exporter):
        consumer = _make_consumer()
        consumer.redis_queue.pop_alert.return_value = dict(_ALERT)
        consumer.telegram.send_alert.return_value = True

        consumer._process_alert_queue()

        span = next(
            (s for s in span_exporter.get_finished_spans()
             if s.name == "notification_sender.alert.send"),
            None,
        )
        assert span is not None
        assert span.attributes.get("notification.provider") == "telegram"

    def test_send_span_success_true(self, span_exporter):
        consumer = _make_consumer()
        consumer.redis_queue.pop_alert.return_value = dict(_ALERT)
        consumer.telegram.send_alert.return_value = True

        consumer._process_alert_queue()

        span = next(
            (s for s in span_exporter.get_finished_spans()
             if s.name == "notification_sender.alert.send"),
            None,
        )
        assert span is not None
        assert span.attributes.get("notification.success") is True

    def test_send_span_success_false_on_failure(self, span_exporter):
        consumer = _make_consumer()
        consumer.redis_queue.pop_alert.return_value = dict(_ALERT)
        consumer.telegram.send_alert.return_value = False

        consumer._process_alert_queue()

        span = next(
            (s for s in span_exporter.get_finished_spans()
             if s.name == "notification_sender.alert.send"),
            None,
        )
        assert span is not None
        assert span.attributes.get("notification.success") is False

    def test_no_span_when_queue_empty(self, span_exporter):
        consumer = _make_consumer()
        consumer.redis_queue.pop_alert.return_value = None

        consumer._process_alert_queue()

        names = [s.name for s in span_exporter.get_finished_spans()]
        assert "notification_sender.alert.send" not in names
