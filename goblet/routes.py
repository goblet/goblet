from collections import OrderedDict 
from ruamel import yaml
import base64
import json 
import logging
import time 
import re

from goblet.handler import Handler
from goblet.client import Client, get_default_project
from goblet.utils import get_g_dir

log = logging.getLogger('goblet.deployer')
log.setLevel(logging.INFO)

class ApiGateway(Handler):
    def __init__(self, app_name, routes={}):
        self.name = self.format_name(app_name)
        self.routes = routes
        self.api_client = self._create_api_client()
        # self.cloudfunction = None

    def format_name(self, name):
        # ([a-z0-9-.]+) for api gateway name
        return name.replace('_','-')
        
    def register_route(self, name, func, kwargs):
        path = kwargs.pop("path")
        methods = kwargs.pop("methods")
        path_entries = self.routes.get(path,{})
        for method in methods:
            if path_entries.get(method):
                raise ValueError(
                    "Duplicate method: '%s' detected for route: '%s'\n"
                    "between view functions: \"%s\" and \"%s\". A specific "
                    "method may only be specified once for "
                    "a particular path." % (
                        method, path, self.routes[path][method].function_name,
                        name)
                )
            entry = RouteEntry(func, name, path, method, **kwargs)
            path_entries[method] = entry
        self.routes[path] = path_entries

    def __call__(self, request, context=None):
        print(request)
        method = request.method
        path = request.path 
        entry = self.routes.get(path,{}).get(method)
        if not entry:
            # test param paths
            for p in self.routes:
                print(p)
                print(path)
                if '{' in p and self._matched_path(p,path):
                    entry = self.routes.get(p,{}).get(method)
        # TODO: better handling
        if not entry:
            raise ValueError(f"No route found for {path} with {method}")
        return entry(request)

    @staticmethod
    def _matched_path(org_path, path):
        split_org = re.sub(r'{[\w]+}', '', org_path).split('/')
        split_path = path.split('/')
        if len(split_path) != len(split_org):
            return False
        for i, item in enumerate(split_org):
            if item and split_path[i] != item:
                return False
        return True

    def _create_api_client(self):
        return Client("apigateway", 'v1beta',calls='projects.locations.apis', parent_schema='projects/{project_id}/locations/global')

    def _create_config_client(self):
        return Client("apigateway", 'v1beta',calls='projects.locations.apis.configs', parent_schema='projects/{project_id}/locations/global/apis/'+self.name)

    def _create_gateway_client(self):
        return Client("apigateway", 'v1beta',calls='projects.locations.gateways', parent_schema='projects/{project_id}/locations/{location_id}')

    def deploy(self):
        resp = self.api_client.execute('create', params={'apiId':self.name})
        time.sleep(10)

        config = {
            "openapiDocuments": [
                { "document": {
                    "path": f'{get_g_dir()}/{self.name}_openapi_spec.yml',
                    "contents": base64.b64encode(open(f'{get_g_dir()}/{self.name}_openapi_spec.yml','rb').read()).decode('utf-8')
                    }
                }
            ]
        }

        config_resp = self._create_config_client().execute('create', params={'apiConfigId':self.name, 'body':config})

        gateway ={
            "apiConfig": f"projects/{get_default_project()}/locations/global/apis/{self.name}/configs/{self.name}",
        }
        gateway_resp = self._create_gateway_client().execute('create', params={'gatewayId':self.name, 'body':gateway})
        log.info(f"deployed api...")
        log.info(f"api endpoint is ")
        return gateway_resp

    def destroy(self):

        # destroy api gateway
        log.info("destroying api gateway......")

        gateway_client = Client("apigateway", 'v1beta',calls='projects.locations.gateways',parent_schema='projects/{project_id}/locations/{location_id}/gateways/' + self.name)
        gateway_client.execute('delete',parent_key="name")

        # destroy api config
        api_client = Client("apigateway", 'v1beta',calls='projects.locations.apis.configs',parent_schema='projects/{project_id}/locations/global/apis/' + self.name + '/configs/' + self.name)
        api_client.execute('delete',parent_key="name")

        # destroy api
        api_client = Client("apigateway", 'v1beta',calls='projects.locations.apis',parent_schema='projects/{project_id}/locations/global/apis/' + self.name)
        api_client.execute('delete',parent_key="name")
        log.info("api gateway successfully destroyed......")


    def generate_openapi_spec(self, cloudfunction):
        spec = OpenApiSpec(self.name, cloudfunction)
        spec.add_apigateway_routes(self.routes)
        with open(f'{get_g_dir()}/{self.name}_openapi_spec.yml', 'w') as f:
            spec.write(f)

class OpenApiSpec:
    def __init__(self, app_name, cloudfunction, version="1.0.0"):
        self.spec = OrderedDict()
        self.app_name = app_name
        self.cloudfunction = cloudfunction
        self.version = version
        self.spec["swagger"] = "2.0"
        self.spec["info"]= {
            "title":self.app_name,
            "description": "Goblet Autogenerated Spec",
            "version": self.version
        }
        self.spec["schemes"] = ["https"]
        self.spec['produces'] = ["application/json"]
        self.spec["paths"] = {}

    def add_apigateway_routes(self, apigateway):
        for path,methods in apigateway.items():
            for method, entry in methods.items():
                self.add_route(entry)

    def add_route(self, entry):
        method_spec = OrderedDict()
        method_spec["x-google-backend"] = {
            "address": self.cloudfunction,
            "protocol": "h2",
            "path_translation": "APPEND_PATH_TO_ADDRESS"
        }
        method_spec["operationId"]=entry.function_name

        params = []
        for param in entry.view_args:
            param_entry = {
                "in":"path",
                "name": param,
                "required": True,
                "type": "string" #TODO: specify type
            } 
            params.append(param_entry)
        if params:
            method_spec["parameters"] = params
        #TODO: add query strings
       
        method_spec["responses"] = {
            '200': {
                "description": "A successful response"
            }
        }
        path_exists = self.spec["paths"].get(entry.uri_pattern)
        if path_exists:
            self.spec["paths"][entry.uri_pattern][entry.method.lower()] = dict(method_spec)
        else:
            self.spec["paths"][entry.uri_pattern] = {
                entry.method.lower(): dict(method_spec)
            }

    def write(self, file):
        yaml.Representer.add_representer(OrderedDict, yaml.Representer.represent_dict)
        yaml.YAML().dump(dict(self.spec), file)

_PARAMS = re.compile(r'{\w+}')

class RouteEntry:

    def __init__(self, route_function, function_name, path, method,
                 api_key_required=None, content_types=None,
                 cors=False, **kwargs):
        self.route_function = route_function
        self.function_name = function_name
        self.uri_pattern = path
        self.method = method
        self.api_key_required = api_key_required
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
            cors = CORSConfig()
        elif cors is False:
            cors = None
        self.cors = cors

    def _extract_view_args(self,path):
        components = path.split('/')
        original_components = self.uri_pattern.split('/')
        matches = 0
        args = {}
        for i, component in enumerate(components):
            if component != original_components[i]:
                args[self.view_args[matches]] = component
                matches +=1 
        return args

    def __call__(self, request):
        #TODO: pass in args and kwargs and options
        args = self._extract_view_args(request.path)
        return self.route_function(**args)

    def _parse_view_args(self):
        if '{' not in self.uri_pattern:
            return []
        # The [1:-1] slice is to remove the braces
        # e.g {foobar} -> foobar
        results = [r[1:-1] for r in _PARAMS.findall(self.uri_pattern)]
        return results

    def __eq__(self, other):
        return self.__dict__ == other.__dict__


class CORSConfig(object):
    """A cors configuration to attach to a route."""

    _REQUIRED_HEADERS = ['Content-Type', 'X-Amz-Date', 'Authorization',
                         'X-Api-Key', 'X-Amz-Security-Token']

    def __init__(self, allow_origin='*', allow_headers=None,
                 expose_headers=None, max_age=None, allow_credentials=None):
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
        return ','.join(sorted(self._allow_headers))

    def get_access_control_headers(self):
        headers = {
            'Access-Control-Allow-Origin': self.allow_origin,
            'Access-Control-Allow-Headers': self.allow_headers
        }
        if self._expose_headers:
            headers.update({
                'Access-Control-Expose-Headers': ','.join(self._expose_headers)
            })
        if self._max_age is not None:
            headers.update({
                'Access-Control-Max-Age': str(self._max_age)
            })
        if self._allow_credentials is True:
            headers.update({
                'Access-Control-Allow-Credentials': 'true'
            })

        return headers

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.get_access_control_headers() == \
                other.get_access_control_headers()
        return False