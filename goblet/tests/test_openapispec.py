from goblet.resources.routes import OpenApiSpec, RouteEntry


class TestOpenApiSpec:

    def test_add_route(self):
        route = RouteEntry(None, "route", "/home", "GET")
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
        route = RouteEntry(None, "route", "/home", "GET")
        route_post = RouteEntry(None, "route", "/home", "POST")
        spec = OpenApiSpec("test", "xyz.cloudfunction")
        spec.add_route(route)
        spec.add_route(route_post)

        assert(spec.spec['paths']['/home'].get('post'))
        assert(spec.spec['paths']['/home'].get('get'))

    def test_add_route_param(self):
        route = RouteEntry(None, "route", "/home/{param}/{param2}", "GET", param_types={'param2':"boolean"})
        spec = OpenApiSpec("test", "xyz.cloudfunction")
        spec.add_route(route)
        params = spec.spec['paths']['/home/{param}/{param2}']['get']['parameters']
        assert(len(params) ==2)
        assert(params[0] == {'in': 'path', 'name': 'param', 'required': True, 'type': 'string'})
        assert(params[1] == {'in': 'path', 'name': 'param2', 'required': True, 'type': 'boolean'})

    def test_security_definitions(self):
        security_def = {
            "your_custom_auth_id":{
                "authorizationUrl": "",
                "flow": "implicit",
                "type": "oauth2",
                "x-google-issuer": "issuer of the token",
                "x-google-jwks_uri": "url to the public key"
            }
        }
        spec = OpenApiSpec("test", "xyz.cloudfunction", security_definitions=security_def)
        assert(spec.spec["securityDefinitions"] == security_def)
