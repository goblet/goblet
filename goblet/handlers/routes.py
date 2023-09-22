from collections import OrderedDict
from marshmallow.schema import Schema
from pydantic import BaseModel
import logging
import os
import re
from typing import get_type_hints
from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin

import goblet

from goblet.handlers.handler import Handler
from goblet.handlers.plugins.pydantic import PydanticPlugin
from goblet.utils import get_g_dir
from goblet.common_cloud_actions import deploy_apigateway, destroy_apigateway
from goblet.permissions import gcp_generic_resource_permissions


log = logging.getLogger("goblet.deployer")
log.setLevel(logging.getLevelName(os.getenv("GOBLET_LOG_LEVEL", "INFO")))


class Routes(Handler):
    """Either cloudrun routes type or Api Gateway instance, which includes api, api config, api gateway instances
    https://cloud.google.com/api-gateway
    """

    resource_type = "routes"
    valid_backends = ["cloudfunction", "cloudrun", "cloudfunctionv2"]
    required_apis = ["cloudfunctions", "apigateway"]
    permissions = [
        "apigateway.operations.get",
        *gcp_generic_resource_permissions("apigateway", "apiconfigs"),
        *gcp_generic_resource_permissions("apigateway", "apis"),
        *gcp_generic_resource_permissions("apigateway", "gateways"),
    ]

    def __init__(
        self,
        name,
        backend,
        versioned_clients=None,
        cors=None,
        resources=None,
        routes_type="apigateway",
    ):
        super(Routes, self).__init__(
            name=name,
            versioned_clients=versioned_clients,
            resources=resources,
            backend=backend,
        )
        self.name = self.format_name(name)
        self.cors = cors or {}
        self.routes_type = routes_type
        self.marshmallow_attribute_function = None

    def format_name(self, name):
        # ([a-z0-9-.]+) for api gateway name
        return name.replace("_", "-")

    def register(self, name, func, kwargs):
        path = kwargs.pop("path")
        methods = kwargs.pop("methods")
        kwargs = kwargs.pop("kwargs")
        if not kwargs.get("cors"):
            kwargs["cors"] = self.cors
        path_entries = self.resources.get(path, {})
        if kwargs["cors"] and "OPTIONS" in methods:
            raise ValueError(
                "Route entry cannot have both cors=True and methods=['OPTIONS', ...] configured."
            )
        for method in methods:
            if path_entries.get(method):
                raise ValueError(
                    "Duplicate method: '%s' detected for route: '%s'\n"
                    'between view functions: "%s" and "%s". A specific '
                    "method may only be specified once for "
                    "a particular path."
                    % (method, path, self.resources[path][method].function_name, name)
                )
            entry = RouteEntry(func, name, path, method, **kwargs)
            path_entries[method] = entry
        # Add OPTIONS if cors set
        if kwargs["cors"]:
            entry = RouteEntry(handle_cors_options, name, path, "OPTIONS", **kwargs)
            path_entries["OPTIONS"] = entry
        self.resources[path] = path_entries

    def __call__(self, request, context=None):
        method = request.method
        path = request.path
        entry = self.resources.get(path, {}).get(method)
        if not entry:
            # search param paths "/{PARAM}"
            for p in self.resources:
                if "{" in p and self._matched_path(p, path):
                    entry = self.resources.get(p, {}).get(method)
        if not entry:
            raise ValueError(f"No route found for {path} with {method}")
        return entry(request)

    @staticmethod
    def _matched_path(org_path, path):
        split_org = re.sub(r"{[\w]+}", "", org_path).split("/")
        split_path = path.split("/")
        if len(split_path) != len(split_org):
            return False
        for i, item in enumerate(split_org):
            if item and split_path[i] != item:
                return False
        return True

    def _deploy(self, source=None, entrypoint=None):
        if (
            self.routes_type != "apigateway"
            and self.backend.resource_type.startswith("cloudfunction")
            and self.versioned_clients.cloudfunctions == "v1"
        ):
            raise ValueError(
                f"Cloudfunctions v1 backend is not supported for routes_type {self.routes_type}"
            )
        if len(self.resources) == 0 or self.routes_type != "apigateway":
            return
        log.info("deploying api......")
        base_url = self.backend.http_endpoint
        self.generate_openapi_spec(base_url)
        if (
            self.config
            and self.config.apiConfig
            and self.config.apiConfig.get("gatewayServiceAccount")
        ):
            self.service_accounts = [self.config.apiConfig.get("gatewayServiceAccount")]
        deploy_apigateway(
            self.name,
            self.config,
            self.versioned_clients,
            f"{get_g_dir()}/{self.name}_openapi_spec.yml",
        )
        return

    def destroy(self):
        if len(self.resources) == 0 or self.routes_type != "apigateway":
            return
        destroy_apigateway(self.name, self.versioned_clients)

    def generate_openapi_spec(self, cloudfunction):
        deadline = self.get_timeout(self.config)
        spec = OpenApiSpec(
            self.name,
            cloudfunction,
            security_definitions=self.config.securityDefinitions,
            security=self.config.security,
            marshmallow_attribute_function=self.marshmallow_attribute_function,
            deadline=deadline,
        )
        spec.add_apigateway_routes(self.resources)
        with open(f"{get_g_dir()}/{self.name}_openapi_spec.yml", "w") as f:
            spec.write(f)

    def get_timeout(self, config):
        # get api gateway timeout
        deadline = (config.api_gateway or {}).get("deadline")
        if self.backend.resource_type == "cloudfunction" and not deadline:
            deadline = (config.cloudfunction or {}).get("timeout")
        if self.backend.resource_type == "cloudfunctionv2" and not deadline:
            deadline = (
                (config.cloudfunction_v2 or {})
                .get("serviceConfig", {})
                .get("timeoutSeconds")
            )
        if self.backend.resource_type == "cloudrun" and not deadline:
            deadline = (config.cloudrun_revision or {}).get("timeout")
        # default deadline to 15 seconds, which is gcp api gateway default
        return deadline or 15


PRIMITIVE_MAPPINGS = {str: "string", bool: "boolean", int: "integer"}


class OpenApiSpec:
    def __init__(
        self,
        app_name,
        cloudfunction,
        version="1.0.0",
        security_definitions=None,
        security=None,
        marshmallow_attribute_function=None,
        deadline=15,
        existing_spec=None,
    ):
        self.options = OrderedDict()
        self.app_name = app_name
        self.cloudfunction = cloudfunction
        self.version = version
        self.deadline = deadline
        self.options["swagger"] = "2.0"
        if security_definitions:
            security_definitions = {**security_definitions}
            self.options["securityDefinitions"] = security_definitions
            self.options["security"] = security or list(
                map(lambda s: {s: []}, security_definitions)
            )
        self.options["schemes"] = ["https"]
        self.options["produces"] = ["application/json"]
        marshmallow_plugin = MarshmallowPlugin()
        pydantic_plugin = PydanticPlugin()
        # Support existing spec. Needs to be version "2.0"
        if existing_spec:
            if not existing_spec.get("swagger") == "2.0":
                raise ValueError("API Gateway only supports swagger 2.0")
            self.component_spec = APISpec(
                title=self.app_name,
                version=self.version,
                openapi_version="2.0",
                **existing_spec,
            )
        else:
            self.component_spec = APISpec(
                title=self.app_name,
                version=self.version,
                openapi_version="2.0",
                # Pydantic plugin needs to go first
                plugins=[pydantic_plugin, marshmallow_plugin],
                **self.options,
            )
        if marshmallow_attribute_function:
            marshmallow_plugin.converter.add_attribute_function(
                marshmallow_attribute_function
            )

    def add_component(self, component, **kwargs):
        if component.__name__ in self.component_spec.components.schemas:
            return
        self.component_spec.components.schema(component.__name__, **kwargs)
        # self.spec["definitions"] = self.component_spec.to_dict()["definitions"]

    def add_apigateway_routes(self, apigateway):
        for path, methods in apigateway.items():
            for method, entry in methods.items():
                self.add_route(entry)

    def get_param_type(self, type_info, only_primititves=False):
        if not type_info:
            return {"type": "string"}
        if type_info in PRIMITIVE_MAPPINGS.keys():
            param_type = {"type": PRIMITIVE_MAPPINGS[type_info]}
        elif issubclass(type_info, Schema) and not only_primititves:
            self.add_component(type_info, schema=type_info)
            param_type = {"$ref": f"#/definitions/{type_info.__name__}"}
        elif issubclass(type_info, BaseModel) and not only_primititves:
            self.add_component(type_info, model=type_info)
            param_type = {"$ref": f"#/definitions/{type_info.__name__}"}
        else:
            raise ValueError(
                f"param_type has type {type_info}. \
                It must be of type {PRIMITIVE_MAPPINGS.values} or a dataclass inheriting from Schema"
            )
        return param_type

    def add_route(self, entry):
        # https://apispec.readthedocs.io/en/latest/quickstart.html add path
        method_spec = OrderedDict()
        method_spec["x-google-backend"] = {
            "address": entry.backend or self.cloudfunction,
            "protocol": "h2",
            "path_translation": "APPEND_PATH_TO_ADDRESS",
            "deadline": entry.deadline or self.deadline,
        }
        method_spec["operationId"] = f"{entry.method.lower()}_{entry.function_name}"

        params = []
        type_hints = get_type_hints(entry.route_function)
        for param in entry.view_args:
            type_info = type_hints.get(param, str)
            param_type = self.get_param_type(type_info, only_primititves=True)

            param_entry = {"in": "path", "name": param, "required": True, **param_type}
            params.append(param_entry)

        if entry.request_body:
            params.append(
                {
                    "in": "body",
                    "name": "requestBody",
                    **self._extract_content(entry.request_body),
                }
            )

        if entry.form_data:
            params.append({"in": "formData", "name": "file", "type": "string"})
            entry.content_types = ["multipart/form-data"]

        if entry.query_params:
            method_spec["parameters"] = []
            for query in entry.query_params:
                if not query.get("schema"):
                    params.append({"in": "query", **query})
                else:
                    params.append(query)
        if params:
            method_spec["parameters"] = params

        return_type = type_hints.get("return")
        content = {}
        if return_type:
            content = self._extract_content(return_type)

        if entry.responses:
            method_spec["responses"] = entry.responses
        else:
            method_spec["responses"] = {
                "200": {"description": "A successful response", **content}
            }
        if entry.security:
            method_spec["security"] = entry.security

        if entry.tags:
            method_spec["tags"] = entry.tags

        if entry.content_types:
            method_spec["consumes"] = entry.content_types

        self.component_spec.path(
            entry.uri_pattern,
            operations={
                entry.method.lower(): dict(
                    **method_spec,
                )
            },
        )

    def _extract_content(self, return_type):
        """
        Return openapi spec response content for the given return type
        """
        if return_type in PRIMITIVE_MAPPINGS.keys():
            return {"schema": {"type": PRIMITIVE_MAPPINGS[return_type]}}
        # list
        if "typing.List" in str(return_type):
            type_info = return_type.__args__[0]
            param_type = self.get_param_type(type_info)
            return {"schema": {"type": "array", "items": {**param_type}}}
        if issubclass(return_type, Schema):
            param_type = self.get_param_type(return_type)
            return {"schema": {**param_type}}
        if issubclass(return_type, BaseModel):
            param_type = self.get_param_type(return_type)
            return {"schema": {**param_type}}

    def add_x_google_backend(self):
        """Add x-google-backend section to custom openapi specs"""
        for path in self.component_spec.options.get("paths", {}).values():
            for method_options in path.values():
                method_options["x-google-backend"] = {
                    "address": self.cloudfunction,
                    "deadline": self.deadline,
                    "path_translation": "APPEND_PATH_TO_ADDRESS",
                    "protocol": "h2",
                }

    def write(self, file):
        file.write(self.component_spec.to_yaml())


_PARAMS = re.compile(r"{\w+}")


class RouteEntry:
    def __init__(
        self,
        route_function,
        function_name,
        path,
        method,
        api_key_required=None,
        content_types=None,
        cors=False,
        **kwargs,
    ):
        self.route_function = route_function
        self.function_name = function_name
        self.uri_pattern = path
        self.method = method
        self.api_key_required = api_key_required
        self.request_body = kwargs.get("request_body")
        self.query_params = kwargs.get("query_params")
        self.form_data = kwargs.get("form_data")
        self.responses = kwargs.get("responses")
        self.backend = kwargs.get("backend")
        self.security = kwargs.get("security")
        self.tags = kwargs.get("tags")
        self.deadline = kwargs.get("deadline")
        #: A list of names to extract from path:
        #: e.g, '/foo/{bar}/{baz}/qux -> ['bar', 'baz']
        self.view_args = self._parse_view_args()
        self.content_types = content_types
        # cors is passed as either a boolean or a CORSConfig object. If it is a
        # boolean it needs to be replaced with a real CORSConfig object to
        # pass the typechecker. None in this context will not inject any cors
        # headers, otherwise the CORSConfig object will determine which
        # headers are injected.
        if cors is True:
            if isinstance(cors, CORSConfig):
                cors = cors
            else:
                cors = CORSConfig()
        elif cors is False:
            cors = None
        self.cors = cors
        self.kwargs = {**kwargs}

    def _extract_view_args(self, path):
        components = path.split("/")
        original_components = self.uri_pattern.split("/")
        matches = 0
        args = {}
        for i, component in enumerate(components):
            if component != original_components[i]:
                args[self.view_args[matches]] = component
                matches += 1
        return args

    def __call__(self, request):
        args = self._extract_view_args(request.path)
        resp = self.route_function(**args)
        return self._apply_cors(resp)

    def _parse_view_args(self):
        if "{" not in self.uri_pattern:
            return []
        # The [1:-1] slice is to remove the braces
        # e.g {foobar} -> foobar
        results = [r[1:-1] for r in _PARAMS.findall(self.uri_pattern)]
        return results

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def _apply_cors(self, resp):
        """Apply cors to Response"""
        if not self.cors:
            return resp
        # Apply to Response Obj
        if isinstance(resp, goblet.Response):
            resp.headers.update(self.cors.get_access_control_headers())
        if isinstance(resp, tuple):
            resp[2].update(self.cors.get_access_control_headers())
        if isinstance(resp, str):
            resp = goblet.Response(resp, headers=self.cors.get_access_control_headers())
        return resp


class CORSConfig(object):
    """A cors configuration to attach to a route."""

    _REQUIRED_HEADERS = ["Content-Type", "Authorization"]

    def __init__(
        self,
        allow_origin="*",
        allow_headers=None,
        expose_headers=None,
        max_age=None,
        allow_credentials=None,
    ):
        self.allow_origin = allow_origin

        if allow_headers is None:
            allow_headers = set(self._REQUIRED_HEADERS)
        else:
            allow_headers = set(allow_headers + self._REQUIRED_HEADERS)
        self._allow_headers = allow_headers

        if expose_headers is None:
            expose_headers = []
        self._expose_headers = expose_headers

        self._max_age = max_age
        self._allow_credentials = allow_credentials

    @property
    def allow_headers(self):
        return ",".join(sorted(self._allow_headers))

    def get_access_control_headers(self):
        headers = {
            "Access-Control-Allow-Origin": self.allow_origin,
            "Access-Control-Allow-Headers": self.allow_headers,
        }
        if self._expose_headers:
            headers.update(
                {"Access-Control-Expose-Headers": ",".join(self._expose_headers)}
            )
        if self._max_age is not None:
            headers.update({"Access-Control-Max-Age": str(self._max_age)})
        if self._allow_credentials is True:
            headers.update({"Access-Control-Allow-Credentials": "true"})

        return headers

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return (
                self.get_access_control_headers() == other.get_access_control_headers()
            )
        return False


def handle_cors_options(**kwargs):
    """Return 200"""
    return "success"
