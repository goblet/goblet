"""
This library builds on the OpenTelemetry WSGI middleware to track web requests
in Goblet applications.

Usage
-----

.. code-block:: python

    from flask import Flask
    from goblet.resource.plugins.instrumentation.opentelemetry_goblet_instrumentation import GobletInstrumentor

    app = Goblet()

    GobletInstrumentor().instrument_app(app)

    @app.route("/")
    def hello():
        return "Hello!"
"""

from goblet import Goblet

from opentelemetry import trace
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

tracer_provider = TracerProvider()
cloud_trace_exporter = CloudTraceSpanExporter()
tracer_provider.add_span_processor(BatchSpanProcessor(cloud_trace_exporter))
trace.set_tracer_provider(tracer_provider)
prop = TraceContextTextMapPropagator()
carrier = {}


class GobletInstrumentor(BaseInstrumentor):
    # pylint: disable=protected-access,attribute-defined-outside-init
    """An instrumentor for Goblet"""

    def instrumentation_dependencies(self):
        # return ("goblet-gcp <= 1.0")
        return ()

    @staticmethod
    def _before_request(request):
        trace.get_tracer(__name__).start_as_current_span(request.path).__enter__()
        prop.inject(carrier=carrier)
        return request

    @staticmethod
    def _after_request(response):
        trace.get_current_span().end()
        return response

    def _instrument(self, app: Goblet):
        """Instrument the library"""
        app.g.tracer = trace.get_tracer(__name__)
        app.g.prop = prop
        app.g.carrier = carrier
        app.before_request()(self._before_request)
        app.after_request()(self._after_request)

    def instrument_app(self, app: Goblet):
        self.instrument(app=app)

    def _uninstrument(self, **kwargs):
        """Uninstrument the library"""
