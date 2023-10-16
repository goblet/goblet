import json
import logging
import sys
import os

from goblet.config import GConfig
import goblet.globals as g
from goblet.decorators import Goblet_Decorators
from goblet.resource_manager import Resource_Manager

from google.cloud.logging.handlers import StructuredLogHandler
from google.cloud.logging_v2.handlers import setup_logging
from typing import List

logging.basicConfig()

log = logging.getLogger("goblet.app")
log.setLevel(logging.getLevelName(os.getenv("GOBLET_LOG_LEVEL", "INFO")))


class Goblet(Goblet_Decorators, Resource_Manager):
    """
    Main class which inherits most of its logic from the Register_Handlers class. Local param is used
    to set the entrypoint for running goblet locally
    """

    def __init__(
        self,
        function_name="goblet",
        backend="cloudfunction",
        local="local",
        cors=None,
        routes_type="apigateway",
        config=None,
        log_level="INFO",
        labels={},
        is_sub_app=False,
    ):
        g.config = GConfig(config or {})
        self.config = g.config
        self.function_name = self.config.function_name or function_name
        self.labels = labels

        self.backend_class = self.get_backend_and_check_versions(backend)
        self.backend = self.backend_class(self)
        self.is_sub_app = is_sub_app

        super(Goblet, self).__init__(
            function_name=self.function_name,
            backend=self.backend,
            cors=cors,
            routes_type=routes_type,
        )
        self.log = logging.getLogger(__name__)
        self.headers = {}
        self.g = G()

        # Setup Local
        module_name = GConfig(config).main_file or "main"
        module_name = module_name.replace(".py", "")
        if local and sys.modules.get(module_name):

            def local_func(request):
                return self(request)

            setattr(sys.modules[module_name], local, local_func)

        # configure logging for local or gcp
        if os.environ.get("X_GOBLET_LOCAL") or os.environ.get("G_HTTP_TEST"):
            logging.basicConfig()
            self.log = logging.getLogger("werkzeug")
        elif not os.environ.get("X-GOBLET-DEPLOY"):
            self.log.handlers.clear()
            handler = StructuredLogHandler()
            setup_logging(
                handler,
                log_level=logging.getLevelName(
                    os.getenv("GOBLET_LOG_LEVEL", log_level)
                ),
            )
            self.log = logging.getLogger(__name__)

    def deploy(
        self,
        skip_handlers=False,
        skip_backend=False,
        skip_infra=False,
        force=False,
        write_config=False,
        stage=None,
        handlers=None,
        infras=None,
    ):
        g.config.update_g_config(values={"labels": self.labels})
        source = None
        backend = self.backend

        if infras or not skip_infra:
            log.info("deploying infrastructure")
            self.deploy_infrastructure(infras)

        infra_config = self.get_infrastructure_config()
        backend.update_config(infra_config, write_config, stage)

        if not skip_backend:
            log.info(f"preparing to deploy with backend {self.backend.resource_type}")
            source = backend.deploy(force=force)

        registered_handlers = self.get_registered_handler_resource_types()

        # checks registered deployable handlers before determining if backend exists
        if (
            registered_handlers
            and skip_backend
            and (handlers or not skip_handlers)
            and not backend.skip_deployment()
            and not backend.get()
        ):
            log.error("backend is not deployed, handlers cannot be deployed. exiting.")
            sys.exit(1)

        if handlers or not skip_handlers:
            log.info("deploying handlers")
            self.deploy_handlers(source, handlers)

    def destroy(
        self,
        all=False,
        skip_infra=False,
        skip_handlers=False,
        skip_backend=False,
        handlers: List[str] = None,
        infras: List[str] = None,
    ):
        """Destroys http cloudfunction and then calls goblet.destroy() to remove handler's infrastructure"""

        if handlers or not skip_handlers:
            log.info("destroying handlers")
            self.destroy_handlers(handlers)

        if not skip_backend:
            self.backend.destroy(all=all)

        if infras or not skip_infra:
            log.info("destroying infrastructure")
            self.destroy_infrastructure(infras)

    def sync(
        self,
        dryrun=False,
        skip_infra=False,
        skip_handlers=False,
        handlers: List[str] = None,
        infras: List[str] = None,
    ):
        if infras or not skip_infra:
            log.info("syncing infrastructure")
            self.sync_infrastructure(dryrun, infras)
        if handlers or not skip_handlers:
            log.info("syncing handlers")
            self.sync_handlers(dryrun, handlers)

    def check_or_enable_services(self, enable=False):
        self.backend._check_or_enable_service(enable)
        for _, v in self.handlers.items():
            v._check_or_enable_service(enable)
        for _, v in self.infrastructure.items():
            v._check_or_enable_service(enable)
        return None

    def get_permissions(self):
        permissions = set()
        permissions.update(self.backend.permissions)
        for _, v in self.handlers.items():
            permissions.update(v.get_permissions())
        for _, v in self.infrastructure.items():
            permissions.update(v.get_permissions())

        permissions = list(permissions)
        permissions.sort()
        return permissions

    def package(self):
        self.backend.zip()

    def deploy_local(self):
        source = None

        log.info("deploying infrastructure locally...")
        self.deploy_infrastructure()

        self.backend.skip_deployment()
        log.info("deploying handlers locally...")
        self.deploy_handlers(source)


def jsonify(*args, **kwargs):
    """
    Helper based on flask jsonify and helps convert lists and dicts into valid reponses.
    """
    indent = None
    separators = (",", ":")
    headers = {"Content-Type": "application/json"}
    headers.update(kwargs.pop("headers", {}))

    options = kwargs.pop("options", {})

    if args and kwargs:
        raise TypeError("jsonify() behavior undefined when passed both args and kwargs")
    elif len(args) == 1:  # single args are passed directly to dumps()
        data = args[0]
    else:
        data = args or kwargs

    if not isinstance(data, (str, bytes)):
        data = json.dumps(data, indent=indent, separators=separators, **options)
    return (data, 200, headers)


class G:
    """
    Global class that allows users to set and pass variables between middlewares.
    """

    pass


def goblet_entrypoint(app, entrypoint="goblet_entrypoint"):
    """
    Wrapper around Goblet app to make it a function, since a recent GCP bug forces the entrypoint to be of type function
    whereas before any type of callable was allowed.
    """
    if sys.modules.get("main"):

        def goblet_entrypoint_wrapper(request, context=None):
            return app(request, context)

        setattr(sys.modules["main"], entrypoint, goblet_entrypoint_wrapper)
