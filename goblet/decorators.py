from __future__ import annotations
import os

from goblet.backends.cloudfunctionv1 import CloudFunctionV1
from goblet.backends.cloudfunctionv2 import CloudFunctionV2
from goblet.backends.cloudrun import CloudRun
from goblet.client import VersionedClients, get_default_location, get_default_project
from goblet.infrastructures.redis import Redis
from goblet.infrastructures.vpcconnector import VPCConnector
from goblet.resources.bq_remote_function import BigQueryRemoteFunction
from goblet.resources.eventarc import EventArc
from goblet.resources.pubsub import PubSub
from goblet.resources.routes import ApiGateway
from goblet.resources.scheduler import Scheduler
from goblet.resources.storage import Storage
from goblet.resources.http import HTTP
from goblet.resources.jobs import Jobs
from goblet.infrastructures.alerts import Alerts

from googleapiclient.errors import HttpError

from warnings import warn

import logging

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

EVENT_TYPES = [
    "all",
    "http",
    "schedule",
    "pubsub",
    "storage",
    "route",
    "eventarc",
    "job",
    "bqremotefunction",
]

SUPPORTED_BACKENDS = {
    "cloudfunction": CloudFunctionV1,
    "cloudfunctionv2": CloudFunctionV2,
    "cloudrun": CloudRun,
}

SUPPORTED_INFRASTRUCTURES = {"redis": Redis, "vpcconnector": VPCConnector}


class DecoratorAPI:
    """Decorator endpoints that are called by the user. Returns _create_registration_function which will trigger the corresponding
    registration function in the Register_Handlers class. For example _create_registration_function with type route will call
    _register_route"""

    def before_request(self, event_type="all"):
        """Function called before request for preeprocessing"""

        if event_type not in EVENT_TYPES:
            raise ValueError(f"{event_type} not in {EVENT_TYPES}")

        def _middleware_wrapper(func):
            self.register_middleware(func, event_type, before_or_after="before")
            return func

        return _middleware_wrapper

    def after_request(self, event_type="all"):
        """Function called after request for postprocessing"""

        if event_type not in EVENT_TYPES:
            raise ValueError(f"{event_type} not in {EVENT_TYPES}")

        def _middleware_wrapper(func):
            self.register_middleware(func, event_type, before_or_after="after")
            return func

        return _middleware_wrapper

    def middleware(self, event_type="all"):
        """Middleware functions that are called before events for preprocessing.
        This is deprecated and will be removed in the future. Use before_request instead"""
        warn(
            "Middleware method is deprecated. Use before_request instead",
            DeprecationWarning,
            stacklevel=2,
        )

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

    def schedule(self, schedule, timezone="UTC", **kwargs):
        """Scheduler job Http trigger"""
        return self._create_registration_function(
            handler_type="schedule",
            registration_kwargs={
                "schedule": schedule,
                "timezone": timezone,
                "kwargs": kwargs,
            },
        )

    def bqremotefunction(self, **kwargs):
        return self._create_registration_function(
            handler_type="bqremotefunction", registration_kwargs={"kwargs": kwargs}
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

    def eventarc(self, topic=None, event_filters=[], **kwargs):
        """Eventarc trigger"""
        return self._create_registration_function(
            handler_type="eventarc",
            registration_kwargs={
                "topic": topic,
                "event_filters": event_filters,
                "kwargs": kwargs,
            },
        )

    def http(self, headers={}):
        """Base http trigger"""
        return self._create_registration_function(
            handler_type="http",
            registration_kwargs={"headers": headers},
        )

    def job(self, name, task_id=0, schedule=None, timezone="UTC", **kwargs):
        """Cloudrun Job"""
        if schedule and task_id != 0:
            raise ValueError("Schedule can only be added to task_id with value 0")
        if kwargs and task_id != 0:
            raise ValueError("Arguments can only be added to task_id with value 0")
        if schedule:
            self._register_handler(
                "schedule",
                f"schedule-job-{name}",
                None,
                kwargs={
                    "schedule": schedule,
                    "timezone": timezone,
                    "kwargs": {
                        "uri": f"https://{get_default_location()}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/{get_default_project()}/jobs/{self.function_name}-{name}:run",
                        "httpMethod": "POST",
                        "authMethod": "oauthToken",
                        **kwargs,
                    },
                },
            )
        return self._create_registration_function(
            handler_type="jobs",
            registration_kwargs={"name": name, "task_id": task_id, "kwargs": kwargs},
        )

    def alert(self, name, conditions, **kwargs):
        """Alert Resource"""
        kwargs["conditions"] = conditions
        return self._register_infrastructure(
            handler_type="alerts",
            kwargs={"name": name, "kwargs": kwargs},
        )

    def redis(self, name, **kwargs):
        """Redis Infrastructure"""
        return self._register_infrastructure(
            handler_type="redis",
            kwargs={"name": name, "kwargs": kwargs},
        )

    def vpcconnector(self, name, **kwargs):
        """VPC Connector Infrastructure"""
        return self._register_infrastructure(
            handler_type="vpcconnector",
            kwargs={"name": name, "kwargs": kwargs},
        )

    def stage(self, stage=None, stages=[]):
        if not stage and not stages:
            raise ValueError("One of stage or stages should be set")

        # Only registers if stage matches.
        def _register_stage(func):
            if os.getenv("STAGE") == stage or os.getenv("STAGE") in stages:
                return func

        return _register_stage

    def _create_registration_function(self, handler_type, registration_kwargs=None):
        def _register_handler(user_handler):
            if user_handler:
                handler_name = user_handler.__name__
                kwargs = registration_kwargs or {}
                self._register_handler(handler_type, handler_name, user_handler, kwargs)
            return user_handler

        return _register_handler

    def _register_handler(self, handler_type, name, func, kwargs, options=None):

        name = kwargs.get("kwargs", {}).get("name") or name
        self.handlers[handler_type].register(name=name, func=func, kwargs=kwargs)

    def _register_infrastructure(self, handler_type, kwargs, options=None):
        self.infrastructure[handler_type].register(
            kwargs["name"], kwargs=kwargs.get("kwargs", {})
        )

    def register_middleware(self, func, event_type="all", before_or_after="before"):
        middleware_list = self.middleware_handlers[before_or_after].get(event_type, [])
        middleware_list.append(func)
        self.middleware_handlers[before_or_after][event_type] = middleware_list


class Register_Handlers(DecoratorAPI):
    """Core Goblet logic. App entrypoint is the __call__ function which routes the request to the corresonding handler class"""

    def __init__(
        self,
        function_name,
        backend,
        cors=None,
        client_versions=None,
        routes_type="apigateway",
        config={},
    ):
        self.client_versions = client_versions

        versioned_clients = VersionedClients(client_versions or {})

        self.handlers = {
            "route": ApiGateway(
                function_name,
                cors=cors,
                backend=backend,
                versioned_clients=versioned_clients,
                routes_type=routes_type,
            ),
            "pubsub": PubSub(
                function_name, backend=backend, versioned_clients=versioned_clients
            ),
            "storage": Storage(
                function_name, backend=backend, versioned_clients=versioned_clients
            ),
            "eventarc": EventArc(
                function_name, backend=backend, versioned_clients=versioned_clients
            ),
            "http": HTTP(
                function_name, backend=backend, versioned_clients=versioned_clients
            ),
            "jobs": Jobs(
                function_name, backend=backend, versioned_clients=versioned_clients
            ),
            "schedule": Scheduler(
                function_name, backend=backend, versioned_clients=versioned_clients
            ),
            "bqremotefunction": BigQueryRemoteFunction(
                function_name, backend=backend, versioned_clients=versioned_clients
            ),
        }

        self.infrastructure = {
            "redis": Redis(
                function_name,
                backend=backend,
                versioned_clients=versioned_clients,
                config=config,
            ),
            "vpcconnector": VPCConnector(
                function_name,
                backend=backend,
                versioned_clients=versioned_clients,
                config=config,
            ),
            "alerts": Alerts(
                function_name,
                backend=backend,
                versioned_clients=versioned_clients,
                config=config,
            ),
        }

        self.middleware_handlers = {
            "before": {},
            "after": {},
        }
        self.current_request = None

    def __call__(self, request, context=None):
        """Goblet entrypoint"""
        self.current_request = request
        self.request_context = context
        event_type = self.get_event_type(request, context)
        # call before request middleware
        request = self._call_middleware(request, event_type, before_or_after="before")
        response = None
        if event_type not in EVENT_TYPES:
            raise ValueError(f"{event_type} not a valid event type")
        if event_type == "job":
            response = self.handlers["jobs"](request, context)
        if event_type == "schedule":
            response = self.handlers["schedule"](request)
        if event_type == "pubsub":
            response = self.handlers["pubsub"](request, context)
        if event_type == "storage":
            # Storage trigger can be made with @eventarc decorator
            try:
                response = self.handlers["storage"](request, context)
            except ValueError:
                event_type = "eventarc"
        if event_type == "route":
            response = self.handlers["route"](request)
        if event_type == "http":
            response = self.handlers["http"](request)
        if event_type == "eventarc":
            response = self.handlers["eventarc"](request)
        if event_type == "bqremotefunction":
            response = self.handlers["bqremotefunction"](request)

        # call after request middleware
        response = self._call_middleware(response, event_type, before_or_after="after")
        return response

    def __add__(self, other):
        for handler in self.handlers:
            self.handlers[handler] += other.handlers[handler]
        return self

    def combine(self, other):
        return self + other

    def get_event_type(self, request, context=None):
        """Parse event type from the event request and context"""
        if os.environ.get("CLOUD_RUN_TASK_INDEX"):
            return "job"
        if context and context.event_type:
            return context.event_type.split(".")[1].split("/")[0]
        if request.headers.get("X-Goblet-Type") == "schedule":
            return "schedule"
        if request.headers.get("Ce-Type") and request.headers.get("Ce-Source"):
            return "eventarc"
        if (
            request.is_json
            and request.json.get("userDefinedContext")
            and request.json["userDefinedContext"].get("X-Goblet-Name")
        ):
            return "bqremotefunction"
        if (
            request.is_json
            and request.get_json(silent=True)
            and request.json.get("subscription")
            and request.json.get("message")
        ):
            return "pubsub"
        if (
            request.path
            and request.path == "/"
            and not request.headers.get("X-Envoy-Original-Path")
        ):
            return "http"
        if request.path:
            return "route"
        return None

    def _call_middleware(self, event, event_type, before_or_after="before"):
        middleware = self.middleware_handlers[before_or_after].get("all", [])
        middleware.extend(self.middleware_handlers[before_or_after].get(event_type, []))
        for m in middleware:
            event = m(event)

        return event

    def get_infrastructure_config(self):
        configs = []
        for _, v in self.infrastructure.items():
            config = v.get_config()
            if config:
                configs.append(config)
        return configs

    def deploy_handlers(self, source, config={}):
        """Call each handlers deploy method"""
        for k, v in self.handlers.items():
            log.info(f"deploying {k}")
            v.deploy(source, entrypoint="goblet_entrypoint", config=config)

    def deploy_infrastructure(self, config={}):
        """Call deploy for each infrastructure"""
        for k, v in self.infrastructure.items():
            log.info(f"deploying {k}")
            v.deploy(config=config)

    def sync(self, dryrun=False):
        """Call each handlers sync method"""
        # Sync Infrastructure
        for _, v in self.infrastructure.items():
            try:
                v.sync(dryrun)
            except HttpError as e:
                if e.resp.status == 403:
                    continue
                raise e

        # Sync Handlers
        for _, v in self.handlers.items():
            try:
                v.sync(dryrun)
            except HttpError as e:
                if e.resp.status == 403:
                    continue
                raise e

    def is_http(self):
        """Is http determines if additional cloudfunctions will be needed since triggers other than http will require their own
        function"""
        # TODO: move to handlers
        if (
            len(self.handlers["route"].resources) > 0
            or len(self.handlers["schedule"].resources) > 0
            or self.handlers["http"].resources
            or self.handlers["pubsub"].is_http()
            or len(self.handlers["bqremotefunction"].resources) > 0
        ):
            return True
        return False

    def get_backend_and_check_versions(self, backend: str, client_versions: dict):
        try:
            backend_class = SUPPORTED_BACKENDS[backend]
        except KeyError:
            raise KeyError(f"Backend {backend} not in supported backends")

        version_key = (
            "cloudfunctions" if backend.startswith("cloudfunction") else backend
        )
        specified_version = client_versions.get(version_key)
        if specified_version:
            if specified_version not in backend_class.supported_versions:
                raise ValueError(
                    f"{version_key} version {self.client_versions[version_key]} "
                    f"not supported. Valid version(s): {', '.join(backend_class.supported_versions)}."
                )
        else:
            # if not set, set to last in list of supported versions (most recent)
            self.client_versions[version_key] = backend_class.supported_versions[-1]

        return backend_class
