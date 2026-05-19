from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def configure_tracing(service_name: str, otlp_endpoint: str) -> None:
    """Configure the global OTel TracerProvider with an OTLP gRPC exporter.

    Call once at service startup (infrastructure layer only).
    Application code imports only opentelemetry-api — no SDK dependency.
    """
    exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    provider = TracerProvider()
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
