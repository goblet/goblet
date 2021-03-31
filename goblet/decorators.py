from goblet.resources.pubsub import PubSub
from goblet.resources.routes import ApiGateway
from goblet.resources.scheduler import Scheduler
import logging

log = logging.getLogger(__name__)

EVENT_TYPES = ["all", 'http', 'schedule', 'pubsub']


class DecoratorAPI:

    def middleware(self, event_type='all'):
        if event_type not in EVENT_TYPES:
            raise ValueError(f"{event_type} not in {EVENT_TYPES}")

        def _middleware_wrapper(func):
            self.register_middleware(func, event_type)
            return func
        return _middleware_wrapper

    def route(self, path, methods=['GET'], **kwargs):
        return self._create_registration_function(
            handler_type='route',
            registration_kwargs={'path': path, 'methods': methods, 'kwargs': kwargs},
        )

    def schedule(self, schedule, **kwargs):
        return self._create_registration_function(
            handler_type='schedule',
            registration_kwargs={'schedule': schedule, 'kwargs': kwargs},
        )

    def topic(self, topic, **kwargs):
        return self._create_registration_function(
            handler_type='pubsub',
            registration_kwargs={'topic': topic, 'kwargs': kwargs},
        )

    def _create_registration_function(self, handler_type,
                                      registration_kwargs=None):
        def _register_handler(user_handler):
            handler_name = user_handler.__name__
            kwargs = registration_kwargs or {}
            self._register_handler(handler_type, handler_name,
                                   user_handler, kwargs)
            return user_handler
        return _register_handler

    def _register_handler(self, handler_type, name,
                          func, kwargs, options=None):
        raise NotImplementedError("_register_handler")

    def register_middleware(self, func, event_type='all'):
        raise NotImplementedError("register_middleware")


class Register_Handlers(DecoratorAPI):

    def __init__(self, function_name):
        self.handlers = {
            "route": ApiGateway(function_name),
            "schedule": Scheduler(function_name),
            "pubsub": PubSub(function_name)
        }
        self.middleware_handlers = {}
        self.current_request = None

    def __call__(self, request, context=None):
        self.current_request = request
        event_type = self.get_event_type(request, context)

        # call middleware
        request = self._call_middleware(request, event_type)

        if event_type == "schedule":
            return self.handlers['schedule'](request)
        if event_type == "pubsub":
            return self.handlers['pubsub'](request, context)
        if event_type == "http":
            self.handlers["route"](request)

        raise ValueError(f"{event_type} not a valid event type")

    def __add__(self, other):
        for handler in self.handlers:
            self.handlers[handler] += other.handlers[handler]
        return self

    def combine(self, other):
        return self + other

    def get_event_type(self, request, context=None):
        if context and context.event_type:
            return context.event_type.split('.')[1].split('/')[0]
        if request.headers.get("X-Goblet-Type") == 'schedule':
            return "schedule"
        return 'http'

    def _call_middleware(self, event, event_type):
        middleware = self.middleware_handlers.get('all', [])
        middleware.extend(self.middleware_handlers.get(event_type, []))
        for m in middleware:
            event = m(event)

        return event

    def _register_handler(self, handler_type, name,
                          func, kwargs, options=None):

        getattr(self, '_register_%s' % handler_type)(
            name=name,
            func=func,
            kwargs=kwargs,
        )

    def deploy(self, sourceUrl):
        for k, v in self.handlers.items():
            log.info(f"deploying {k}")
            v.deploy(sourceUrl, self.entrypoint)

    def destroy(self):
        for k, v in self.handlers.items():
            log.info(f"deploying {k}")
            v.destroy()

    def is_http(self):
        if len(self.handlers["route"].routes) > 0 or len(self.handlers["schedule"].jobs) > 0:
            return True
        return False

    def register_middleware(self, func, event_type='all'):
        middleware_list = self.middleware_handlers.get(event_type, [])
        middleware_list.append(func)
        self.middleware_handlers[event_type] = middleware_list

    def _register_route(self, name, func, kwargs):
        self.handlers["route"].register_route(name=name, func=func, kwargs=kwargs)

    def _register_schedule(self, name, func, kwargs):
        self.handlers["schedule"].register_job(name=name, func=func, kwargs=kwargs)

    def _register_pubsub(self, name, func, kwargs):
        self.handlers["pubsub"].register_topic(name=name, func=func, kwargs=kwargs)
