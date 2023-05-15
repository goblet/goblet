from __future__ import annotations
import os
import logging
from googleapiclient.errors import HttpError

from goblet.client import VersionedClients

from goblet.backends.cloudfunctionv1 import CloudFunctionV1
from goblet.backends.cloudfunctionv2 import CloudFunctionV2
from goblet.backends.cloudrun import CloudRun

from goblet.handlers.bq_remote_function import BigQueryRemoteFunction
from goblet.handlers.eventarc import EventArc
from goblet.handlers.pubsub import PubSub
from goblet.handlers.routes import Routes
from goblet.handlers.scheduler import Scheduler
from goblet.handlers.cloudtasktarget import CloudTaskTarget
from goblet.handlers.storage import Storage
from goblet.handlers.http import HTTP
from goblet.handlers.jobs import Jobs

from goblet.infrastructures.redis import Redis
from goblet.infrastructures.vpcconnector import VPCConnector
from goblet.infrastructures.alerts import Alerts
from goblet.infrastructures.apigateway import ApiGateway
from goblet.infrastructures.cloudtask import CloudTaskQueue

import goblet.globals as g

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
    "cloudtasktarget",
]

SUPPORTED_BACKENDS = {
    "cloudfunction": CloudFunctionV1,
    "cloudfunctionv2": CloudFunctionV2,
    "cloudrun": CloudRun,
}

SUPPORTED_INFRASTRUCTURES = {
    "redis": Redis,
    "vpcconnector": VPCConnector,
    "cloudtaskqueue": CloudTaskQueue,
}


class Resource_Manager:
    """Core Goblet logic. App entrypoint is the __call__ function which routes the request to the corresonding handler class"""

    def __init__(
        self,
        function_name,
        backend,
        cors=None,
        routes_type="apigateway",
    ):
        self.app_list = []

        self.handlers = {
            "cloudtasktarget": CloudTaskTarget(function_name, backend=backend),
            "route": Routes(
                function_name,
                cors=cors,
                backend=backend,
                routes_type=routes_type,
            ),
            "pubsub": PubSub(function_name, backend=backend),
            "storage": Storage(function_name, backend=backend),
            "eventarc": EventArc(function_name, backend=backend),
            "http": HTTP(function_name, backend=backend),
            "jobs": Jobs(function_name, backend=backend),
            "schedule": Scheduler(function_name, backend=backend),
            "bqremotefunction": BigQueryRemoteFunction(function_name, backend=backend),
        }

        self.infrastructure = {
            "cloudtaskqueue": CloudTaskQueue(
                function_name,
                backend=backend,
            ),
            "redis": Redis(
                function_name,
                backend=backend,
            ),
            "vpcconnector": VPCConnector(
                function_name,
                backend=backend,
            ),
            "alerts": Alerts(function_name, backend=backend),
            "apigateway": ApiGateway(function_name, backend=backend),
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

        # set var's for added apps
        for added_app in self.app_list:
            added_app.current_request = request
            added_app.request_context = context

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
        if event_type == "cloudtasktarget":
            response = self.handlers["cloudtasktarget"](request)

        # call after request middleware
        response = self._call_middleware(response, event_type, before_or_after="after")
        return response

    def __add__(self, other):
        self.app_list.append(other)
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
        if request.headers.get("User-Agent") == "Google-Cloud-Tasks":
            return "cloudtasktarget"
        if request.headers.get("Ce-Type") and request.headers.get("Ce-Source"):
            return "eventarc"
        if (
            request.is_json
            and isinstance(request.json, dict)
            and request.json.get("userDefinedContext")
            and request.json["userDefinedContext"].get("X-Goblet-Name")
        ):
            return "bqremotefunction"
        if (
            request.is_json
            and request.get_json(silent=True)
            and isinstance(request.json, dict)
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

    def deploy_handlers(self, source):
        """Call each handlers deploy method"""
        for k, v in self.handlers.items():
            log.info(f"deploying {k}")
            v.deploy(source, entrypoint="goblet_entrypoint")

    def deploy_infrastructure(self):
        """Call deploy for each infrastructure"""
        for k, v in self.infrastructure.items():
            log.info(f"deploying {k}")
            v.deploy()

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
            or len(self.handlers["cloudtasktarget"].resources) > 0
        ):
            return True
        return False

    def get_backend_and_check_versions(self, backend: str):
        client_versions = VersionedClients().client_versions
        try:
            backend_class = SUPPORTED_BACKENDS[backend]
        except KeyError:
            raise KeyError(f"Backend {backend} not in supported backends")

        version_key = (
            "cloudfunctions" if backend.startswith("cloudfunction") else backend
        )
        # User selected version
        specified_version = None
        if (
            g.config
            and g.config.client_versions
            and isinstance(g.config.client_versions, dict)
        ):
            specified_version = g.config.client_versions.get(version_key)
        if specified_version:
            if specified_version not in backend_class.supported_versions:
                raise ValueError(
                    f"{version_key} version {client_versions[version_key]} "
                    f"not supported. Valid version(s): {', '.join(backend_class.supported_versions)}."
                )
        else:
            # if not set, set to last in list of supported versions (most recent)
            client_versions[version_key] = backend_class.supported_versions[-1]

        return backend_class
