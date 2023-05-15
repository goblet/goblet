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

logging.basicConfig()

log = logging.getLogger("goblet.app")
log.setLevel(logging.INFO)


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
        log_level=logging.INFO,
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
            setup_logging(handler, log_level=log_level)
            self.log = logging.getLogger(__name__)

    def deploy(
        self,
        skip_resources=False,
        skip_backend=False,
        skip_infra=False,
        force=False,
        write_config=False,
        stage=None,
    ):
        g.config.update_g_config(values={"labels": self.labels})
        source = None
        backend = self.backend
        if not skip_infra:
            log.info("deploying infrastructure")
            self.deploy_infrastructure()

        infra_config = self.get_infrastructure_config()
        backend.update_config(infra_config, write_config, stage)

        if not skip_backend:
            log.info(f"preparing to deploy with backend {self.backend.resource_type}")
            source = backend.deploy(force=force)
        if not skip_resources:
            self.deploy_handlers(source)

    def destroy(self, all=False, skip_infra=False):
        """Destroys http cloudfunction and then calls goblet.destroy() to remove handler's infrastructure"""
        for k, v in self.handlers.items():
            log.info(f"destroying {k}")
            v.destroy()
        self.backend.destroy(all=all)

        if not skip_infra:
            for k, v in self.infrastructure.items():
                log.info(f"destroying {k}")
                v.destroy()

    def check_or_enable_services(self, enable=False):
        self.backend._check_or_enable_service(enable)
        for _, v in self.handlers.items():
            v._check_or_enable_service(enable)
        for _, v in self.infrastructure.items():
            v._check_or_enable_service(enable)
        return None

    def package(self):
        self.backend.zip()


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
