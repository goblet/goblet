from unittest.mock import Mock
from goblet import Goblet
from goblet.resources.routes import ApiGateway
from goblet.deploy import Deployer
from goblet.test_utils import get_responses, get_response


class TestRoutes:

    def test_add_base_route(self):
        app = Goblet(function_name="goblet_example")

        @app.route('/home')
        def dummy_function(self):
            return True

        gateway = app.handlers["route"]
        assert(len(gateway.routes) == 1)
        route_entry = gateway.routes['/home']['GET']
        assert(route_entry.method == 'GET')
        assert(route_entry.function_name == 'dummy_function')
        assert(route_entry.uri_pattern == '/home')
        assert(route_entry.route_function == dummy_function)

    def test_add_route_path_params(self):
        app = Goblet(function_name="goblet_example")

        @app.route('/home/{home_id}', content_types={'home_id': 'boolean'})
        def dummy_function(self, home_id):
            return True

        gateway = app.handlers["route"]
        assert(len(gateway.routes) == 1)
        route_entry = gateway.routes['/home/{home_id}']['GET']
        assert(route_entry.method == 'GET')
        assert(route_entry.function_name == 'dummy_function')
        assert(route_entry.uri_pattern == '/home/{home_id}')
        assert(route_entry.route_function == dummy_function)

    def test_add_multiple_methods(self):
        app = Goblet(function_name="goblet_example")

        @app.route('/home', methods=['POST', 'GET'])
        def dummy_function(self):
            return True

        @app.route('/home', methods=['PUT'])
        def dummy_function2(self):
            return True
        gateway = app.handlers["route"]
        assert(len(gateway.routes) == 1)
        assert(gateway.routes['/home']['GET'])
        assert(gateway.routes['/home']['POST'])
        assert(gateway.routes['/home']['PUT'])
        assert(gateway.routes['/home']['GET'].route_function == gateway.routes['/home']['POST'].route_function)
        assert(gateway.routes['/home']['GET'].route_function != gateway.routes['/home']['PUT'].route_function)

    def test_add_multiple_routes(self):
        app = Goblet(function_name="goblet_example")

        @app.route('/home')
        def dummy_function(self, home_id):
            return True

        @app.route('/home2')
        def dummy_function2(self, home_id):
            return True
        gateway = app.handlers["route"]
        assert(len(gateway.routes) == 2)
        assert(gateway.routes['/home']['GET'])
        assert(gateway.routes['/home2']['GET'])

    def test_call_route(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "TEST_PROJECT")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        app = Goblet(function_name="goblet_example")
        mock = Mock()
        mock_param = Mock()

        @app.route('/test')
        def mock_function():
            mock()
            return True

        @app.route('/test/{param}', methods=['POST'])
        def mock_function2(param):
            mock_param(param)
            return True

        mock_event1 = Mock()
        mock_event1.path = '/test'
        mock_event1.method = 'GET'
        mock_event1.headers = {"X-Envoy-Original-Path": True}
        app(mock_event1, None)

        mock_event2 = Mock()
        mock_event2.path = '/test/param'
        mock_event2.method = 'POST'
        mock_event2.headers = {"X-Envoy-Original-Path": True}
        app(mock_event2, None)

        assert(mock.call_count == 1)
        mock_param.assert_called_once_with('param')

    def test_deploy_routes(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "routes-deploy")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

        app = Goblet(function_name="goblet_routes")
        setattr(app, "entrypoint", 'app')

        @app.route('/')
        def dummy_function(data):
            return

        Deployer().deploy(app, force=True)

        post_api = get_response('routes-deploy', 'post-v1-projects-goblet-locations-global-apis_1.json')
        post_config = get_response('routes-deploy', 'post-v1-projects-goblet-locations-global-apis-goblet-routes-configs_1.json')
        post_gw = get_response('routes-deploy', 'post-v1-projects-goblet-locations-us-central1-gateways_1.json')
        get_gw = get_response('routes-deploy', 'get-v1-projects-goblet-locations-us-central1-gateways-goblet-routes_1.json')

        assert(post_api['body']['metadata']['verb'] == 'create')
        assert(post_api['body']['metadata']['target'].endswith('goblet-routes'))
        assert(post_config['body']['metadata']['verb'] == 'create')
        assert(post_config['body']['metadata']['target'].endswith('goblet-routes'))
        assert(post_gw['body']['metadata']['verb'] == 'create')
        assert(post_gw['body']['metadata']['target'].endswith('goblet-routes'))
        assert(get_gw['body']['state'] == 'ACTIVE')
        assert(get_gw['body']['displayName'] == 'goblet-routes')

    def test_destroy_routes(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "routes-destroy")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

        apigw = ApiGateway('goblet_routes', routes=['not_empty'])
        apigw.destroy()

        responses = get_responses('routes-destroy')

        assert(responses[0]['body']['metadata']['verb'] == 'delete')
        assert(responses[0]['body']['metadata']['target'].endswith('goblet-routes'))
        assert(responses[1]['body']['metadata']['verb'] == 'delete')
        assert(responses[1]['body']['metadata']['target'].endswith('goblet-routes'))
        assert(responses[2]['body']['metadata']['verb'] == 'delete')
        assert(responses[2]['body']['metadata']['target'].endswith('goblet-routes'))


class TestApiGateway:

    def test_path_param_matching(self):
        gw = ApiGateway('test')
        assert(gw._matched_path('/home/{home_id}', '/home/5'))
        assert(not gw._matched_path('/home/{home_id}', '/home/5/fail'))
