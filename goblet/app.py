import json
import logging
import sys

from goblet.client import DEFAULT_CLIENT_VERSIONS
from goblet.config import GConfig
from goblet.decorators import Register_Handlers

logging.basicConfig()

log = logging.getLogger("goblet.app")
log.setLevel(logging.INFO)


class Goblet(Register_Handlers):
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
        client_versions=None,
        routes_type="apigateway",
    ):
        self.client_versions = DEFAULT_CLIENT_VERSIONS
        self.client_versions.update(client_versions or {})
        self.backend = backend
        self.backend_class = self.get_backend_and_check_versions(
            backend, client_versions or {}
        )
        # self.client_versions[self.backend_class.resource_type] = self.backend_class.version
        self.function_name = GConfig().function_name or function_name

        super(Goblet, self).__init__(
            function_name=self.function_name,
            backend=backend,
            cors=cors,
            client_versions=self.client_versions,
            routes_type=routes_type,
        )
        self.log = logging.getLogger(__name__)
        self.headers = {}
        self.g = G()

        # Setup Local
        module_name = GConfig().main_file or "main"
        module_name = module_name.replace(".py", "")
        if local and sys.modules.get(module_name):
            self.log = logging.getLogger("werkzeug")

            def local_func(request):
                return self(request)

            setattr(sys.modules[module_name], local, local_func)

    def deploy(self, skip_function=False, only_function=False, config={}, force=False):
        source = None
        if not skip_function:
            log.info(f"preparing to deploy with backend {self.backend_class.__name__}")
            source = self.backend_class(self).deploy(force=force, config=config)
        if not only_function:
            self.deploy_handlers(source, config=config)

    def destroy(self, all=False):
        """Destroys http cloudfunction and then calls goblet.destroy() to remove handler's infrastructure"""
        for k, v in self.handlers.items():
            log.info(f"destroying {k}")
            v.destroy()
        self.backend_class(self).destroy(all=all)

    def package(self):
        self.backend_class(self).zip()


def jsonify(*args, **kwargs):
    """
    Helper based on flask jsonify and helsp convert lists and dicts into valid reponses.
    """
    indent = None
    separators = (",", ":")
    headers = {"Content-Type": "application/json"}
    headers.update(kwargs.get("headers", {}))

    if args and kwargs:
        raise TypeError("jsonify() behavior undefined when passed both args and kwargs")
    elif len(args) == 1:  # single args are passed directly to dumps()
        data = args[0]
    else:
        data = args or kwargs

    if not isinstance(data, (str, bytes)):
        data = json.dumps(data, indent=indent, separators=separators)
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
