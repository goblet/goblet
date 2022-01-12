from goblet.resources.pubsub import PubSub
from goblet.resources.routes import ApiGateway
from goblet.resources.scheduler import Scheduler
from goblet.resources.storage import Storage
from goblet.resources.http import HTTP

import logging

log = logging.getLogger(__name__)

EVENT_TYPES = ["all", "http", "schedule", "pubsub", "storage", "route"]
BACKEND_TYPES = ["cloudfunction", "cloudrun"]


class DecoratorAPI:
    """Decorator endpoints that are called by the user. Returns _create_registration_function which will trigger the corresponding
    registration function in the Register_Handlers class. For example _create_registration_function with type route will call
    _register_route"""

    def middleware(self, event_type="all"):
        """Middleware functions that are called before events for preprocessing"""
        if event_type not in EVENT_TYPES:
            raise ValueError(f"{event_type} not in {EVENT_TYPES}")

        def _middleware_wrapper(func):
            self.register_middleware(func, event_type)
            return func

        return _middleware_wrapper

    def route(self, path, methods=["GET"], **kwargs):
        """Api Gateway route"""
        return self._create_registration_function(
            handler_type="route",
            registration_kwargs={"path": path, "methods": methods, "kwargs": kwargs},
        )

    def schedule(self, schedule, **kwargs):
        """Scheduler job Http trigger"""
        return self._create_registration_function(
            handler_type="schedule",
            registration_kwargs={"schedule": schedule, "kwargs": kwargs},
        )

    def topic(self, topic, **kwargs):
        """Pubsub topic trigger"""
        return self._create_registration_function(
            handler_type="pubsub",
            registration_kwargs={"topic": topic, "kwargs": kwargs},
        )

    def storage(self, bucket, event_type, name=None):
        """Storage event trigger"""
        return self._create_registration_function(
            handler_type="storage",
            registration_kwargs={
                "bucket": bucket,
                "event_type": event_type,
                "name": name,
            },
        )

    def http(self, headers={}):
        """Base http trigger"""
        return self._create_registration_function(
            handler_type="http",
            registration_kwargs={"headers": headers},
        )

    def _create_registration_function(self, handler_type, registration_kwargs=None):
        def _register_handler(user_handler):
            handler_name = user_handler.__name__
            kwargs = registration_kwargs or {}
            self._register_handler(handler_type, handler_name, user_handler, kwargs)
            return user_handler

        return _register_handler

    def _register_handler(self, handler_type, name, func, kwargs, options=None):
        raise NotImplementedError("_register_handler")

    def register_middleware(self, func, event_type="all"):
        raise NotImplementedError("register_middleware")


class Register_Handlers(DecoratorAPI):
    """Core Goblet logic. App entrypoint is the __call__ function which routes the request to the corresonding handler class"""

    def __init__(self, function_name, backend="cloudfunction", cors=None):
        self.backend = backend
        if backend not in BACKEND_TYPES:
            raise ValueError(f"{backend} not a valid backend")

        self.handlers = {
            "route": ApiGateway(function_name, cors=cors, backend=backend),
            "schedule": Scheduler(function_name, backend=backend),
            "pubsub": PubSub(function_name, backend=backend),
            "storage": Storage(function_name, backend=backend),
            "http": HTTP(backend=backend),
        }
        self.middleware_handlers = {}
        self.current_request = None

    def __call__(self, request, context=None):
        """Goblet entrypoint"""
        self.current_request = request
        event_type = self.get_event_type(request, context)

        # call middleware
        request = self._call_middleware(request, event_type)

        if event_type == "schedule":
            return self.handlers["schedule"](request)
        if event_type == "pubsub":
            return self.handlers["pubsub"](request, context)
        if event_type == "storage":
            return self.handlers["storage"](request, context)
        if event_type == "route":
            return self.handlers["route"](request)
        if event_type == "http":
            return self.handlers["http"](request)

        raise ValueError(f"{event_type} not a valid event type")

    def __add__(self, other):
        for handler in self.handlers:
            self.handlers[handler] += other.handlers[handler]
        return self

    def combine(self, other):
        return self + other

    def get_event_type(self, request, context=None):
        """Parse event type from the event request and context"""
        if context and context.event_type:
            return context.event_type.split(".")[1].split("/")[0]
        if request.headers.get("X-Goblet-Type") == "schedule":
            return "schedule"
        if (
            request.path
            and request.path == "/"
            and not request.headers.get("X-Envoy-Original-Path")
        ):
            return "http"
        if request.path:
            return "route"
        return None

    def _call_middleware(self, event, event_type):
        middleware = self.middleware_handlers.get("all", [])
        middleware.extend(self.middleware_handlers.get(event_type, []))
        for m in middleware:
            event = m(event)

        return event

    def _register_handler(self, handler_type, name, func, kwargs, options=None):

        getattr(self, "_register_%s" % handler_type)(
            name=name,
            func=func,
            kwargs=kwargs,
        )

    def deploy(self, source_url):
        """Call each handlers deploy method"""
        for k, v in self.handlers.items():
            log.info(f"deploying {k}")
            v.deploy(source_url, entrypoint="goblet_entrypoint")

    def destroy(self):
        """Call each handlers destroy method"""
        for k, v in self.handlers.items():
            log.info(f"destroying {k}")
            v.destroy()

    def is_http(self):
        """Is http determines if additional cloudfunctions will be needed since triggers other than http will require their own
        function"""
        if (
            len(self.handlers["route"].resources) > 0
            or len(self.handlers["schedule"].resources) > 0
            or self.handlers["http"].resources
        ):
            return True
        return False

    def register_middleware(self, func, event_type="all"):
        middleware_list = self.middleware_handlers.get(event_type, [])
        middleware_list.append(func)
        self.middleware_handlers[event_type] = middleware_list

    def _register_http(self, name, func, kwargs):
        self.handlers["http"].register_http(func, kwargs=kwargs)

    def _register_route(self, name, func, kwargs):
        self.handlers["route"].register_route(name=name, func=func, kwargs=kwargs)

    def _register_schedule(self, name, func, kwargs):
        name = kwargs.get("kwargs", {}).get("name") or name
        self.handlers["schedule"].register_job(name=name, func=func, kwargs=kwargs)

    def _register_pubsub(self, name, func, kwargs):
        self.handlers["pubsub"].register_topic(name=name, func=func, kwargs=kwargs)

    def _register_storage(self, name, func, kwargs):
        name = kwargs.get("name") or kwargs["bucket"]
        self.handlers["storage"].register_bucket(name=name, func=func, kwargs=kwargs)
