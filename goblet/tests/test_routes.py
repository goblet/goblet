from goblet import Goblet
from goblet.resources.routes import ApiGateway

class TestRoutes:

    
    def test_add_base_route(self):
        app = Goblet(function_name="goblet_example",region='us-central-1')

        @app.route('/home')
        def dummy_function(self):
            return True
        
        gateway = app.handlers["route"]
        assert(len(gateway.routes) == 1)
        route_entry = gateway.routes['/home']['GET'] 
        assert(route_entry.method=='GET')
        assert(route_entry.function_name=='dummy_function')
        assert(route_entry.uri_pattern=='/home')
        assert(route_entry.route_function==dummy_function)

    def test_add_route_path_params(self):
        app = Goblet(function_name="goblet_example",region='us-central-1')

        @app.route('/home/{home_id}', content_types={'home_id':'boolean'})
        def dummy_function(self, home_id):
            return True
        
        gateway = app.handlers["route"]
        assert(len(gateway.routes) == 1)
        route_entry = gateway.routes['/home/{home_id}']['GET'] 
        assert(route_entry.method=='GET')
        assert(route_entry.function_name=='dummy_function')
        assert(route_entry.uri_pattern=='/home/{home_id}')
        assert(route_entry.route_function==dummy_function) 

    def test_add_multiple_methods(self):
        app = Goblet(function_name="goblet_example",region='us-central-1')

        @app.route('/home', methods=['POST','GET'])
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
        app = Goblet(function_name="goblet_example",region='us-central-1')

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


class TestApiGateway:

    def test_path_param_matching(self):
        gw = ApiGateway('test')
        assert(gw._matched_path('/home/{home_id}', '/home/5'))
        assert(not gw._matched_path('/home/{home_id}', '/home/5/fail'))