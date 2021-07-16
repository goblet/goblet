from typing import List
from marshmallow import Schema, fields
from goblet.resources.routes import OpenApiSpec, RouteEntry


def dummy():
    pass


class DummySchema(Schema):
    id = fields.Int()
    flt = fields.Float()


class TestOpenApiSpec:

    def test_add_route(self):
        route = RouteEntry(dummy, "route", "/home", "GET")
        spec = OpenApiSpec("test", "xyz.cloudfunction")
        spec.add_route(route)
        expected_json = {
            '/home': {
                'get': {
                    'x-google-backend': {
                        'address': 'xyz.cloudfunction',
                        'protocol': 'h2',
                        'path_translation': 'APPEND_PATH_TO_ADDRESS'
                    },
                    'operationId': 'route',
                    'responses': {
                        '200': {
                            'description': 'A successful response'
                        }
                    }
                }
            }
        }
        assert(spec.spec['paths'] == expected_json)

    def test_add_route_post(self):
        route = RouteEntry(dummy, "route", "/home", "GET")
        route_post = RouteEntry(dummy, "route", "/home", "POST")
        spec = OpenApiSpec("test", "xyz.cloudfunction")
        spec.add_route(route)
        spec.add_route(route_post)

        assert(spec.spec['paths']['/home'].get('post'))
        assert(spec.spec['paths']['/home'].get('get'))

    def test_security_definitions(self):
        security_def = {
            "your_custom_auth_id": {
                "authorizationUrl": "",
                "flow": "implicit",
                "type": "oauth2",
                "x-google-issuer": "issuer of the token",
                "x-google-jwks_uri": "url to the public key"
            }
        }
        spec = OpenApiSpec("test", "xyz.cloudfunction", security_definitions=security_def)
        assert(spec.spec["securityDefinitions"] == security_def)
        assert(spec.spec["security"] == [{"your_custom_auth_id": []}])

    def test_security_config(self):
        security_def = {
            "your_custom_auth_id": {
                "authorizationUrl": "",
                "flow": "implicit",
                "type": "oauth2",
                "x-google-issuer": "issuer of the token",
                "x-google-jwks_uri": "url to the public key"
            }
        }
        spec = OpenApiSpec("test", "xyz.cloudfunction", security_definitions=security_def, security=[{"custom": []}])
        assert(spec.spec["securityDefinitions"] == security_def)
        assert(spec.spec["security"] == [{"custom": []}])

    def test_add_primitive_types(self):
        def prim_typed(param: str, param2: bool) -> int:
            return 200

        route = RouteEntry(prim_typed, "route", "/home/{param}/{param2}", "GET")
        spec = OpenApiSpec("test", "xyz.cloudfunction")
        spec.add_route(route)
        params = spec.spec['paths']['/home/{param}/{param2}']['get']['parameters']
        assert(len(params) == 2)
        assert(params[0] == {'in': 'path', 'name': 'param', 'required': True, 'type': 'string'})
        assert(params[1] == {'in': 'path', 'name': 'param2', 'required': True, 'type': 'boolean'})
        response_content = spec.spec['paths']['/home/{param}/{param2}']['get']['responses']['200']["schema"]
        assert response_content == {'type': 'integer'}

    def test_return_schema_regular(self):
        def schema_typed() -> DummySchema:
            return DummySchema()

        route = RouteEntry(schema_typed, "route", "/home", "GET")
        spec = OpenApiSpec("test", "xyz.cloudfunction")
        spec.add_route(route)
        response_content = spec.spec['paths']['/home']['get']['responses']['200']['schema']
        assert response_content == {'$ref': '#/definitions/DummySchema'}
        assert len(spec.spec['definitions']["DummySchema"]["properties"]) == 2

    def test_return_lists(self):
        def schema_typed_list() -> List[DummySchema]:
            return []

        route = RouteEntry(schema_typed_list, "route", "/home", "GET")
        spec = OpenApiSpec("test", "xyz.cloudfunction")
        spec.add_route(route)
        response_content = spec.spec['paths']['/home']['get']['responses']['200']['schema']
        assert response_content == {"type": "array", "items": {'$ref': '#/definitions/DummySchema'}}
        assert len(spec.spec['definitions']["DummySchema"]["properties"]) == 2

        def prim_typed_list() -> List[str]:
            return []

        route = RouteEntry(prim_typed_list, "route", "/home", "GET")
        spec = OpenApiSpec("test", "xyz.cloudfunction")
        spec.add_route(route)
        response_content = spec.spec['paths']['/home']['get']['responses']['200']['schema']
        assert response_content == {"type": "array", "items": {'type': 'string'}}
        assert len(spec.spec['definitions']) == 0

    def test_custom_response(self):
        route = RouteEntry(dummy, "route", "/home", "GET", responses={'400': {'description': '400'}})
        spec = OpenApiSpec("test", "xyz.cloudfunction")
        spec.add_route(route)
        response = spec.spec['paths']['/home']['get']['responses']
        assert response['400'] == {'description': '400'}

    def test_request_body(self):
        route = RouteEntry(dummy, "route", "/home", "GET", request_body={'schema': {"type": "array", "items": {'type': 'string'}}})
        spec = OpenApiSpec("test", "xyz.cloudfunction")
        spec.add_route(route)
        params = spec.spec['paths']['/home']['get']['parameters'][0]
        assert params == {'in': 'body', 'name': 'requestBody', 'schema': {'type': 'array', 'items': {'type': 'string'}}}

    def test_form_data(self):
        route = RouteEntry(dummy, "route", "/home", "GET", form_data=True)
        spec = OpenApiSpec("test", "xyz.cloudfunction")
        spec.add_route(route)
        params = spec.spec['paths']['/home']['get']['parameters'][0]
        assert params == {'in': 'formData', 'name': 'file', 'type': 'file'}

    def test_custom_backend(self):
        route = RouteEntry(dummy, "route", "/home", "GET", form_data=True, backend="CLOUDRUN/URL")
        spec = OpenApiSpec("test", "xyz.cloudfunction")
        spec.add_route(route)
        entry = spec.spec['paths']['/home']['get']
        assert entry["x-google-backend"]["address"] == "CLOUDRUN/URL"
