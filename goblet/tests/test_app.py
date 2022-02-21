from urllib import response
from goblet import jsonify, Response, Goblet
from unittest.mock import Mock


class TestJsonify:
    headers = {"Content-Type": "application/json"}

    def test_string(self):
        resp = jsonify("hello")
        assert resp == ("hello", 200, self.headers)

    def test_dict(self):
        resp = jsonify({"a": "b"})
        assert resp == ('{"a":"b"}', 200, self.headers)

    def test_array(self):
        resp = jsonify([1, 2])
        assert resp == ("[1,2]", 200, self.headers)


class TestResponse:
    def test_headers(self):
        def start_response_headers(status, response_headers, exc_info=None):
            assert response_headers == [("Content-Type", "json")]

        r = Response("test", {"Content-Type": "json"})
        assert r({}, start_response_headers) == ["test"]

    def test_status(self):
        def start_response_status(status, response_headers, exc_info=None):
            assert status == 401

        r = Response("test", status_code=401)
        assert r({}, start_response_status) == ["test"]


class TestDecoraters:
    def test_add(self):
        app1 = Goblet("test")
        app2 = Goblet("test")

        @app1.route("/home")
        @app2.route("/home2")
        @app1.schedule("* * * * *")
        def dummy_function(self, home_id):
            return True

        @app2.schedule("1 * * * *")
        def dummy_function2(self, home_id):
            return True

        app1 + app2

        assert list(app1.handlers["route"].resources.keys()) == ["/home", "/home2"]
        assert list(app1.handlers["schedule"].resources.keys()) == [
            "dummy_function",
            "dummy_function2",
        ]

    def test_combine(self):
        app1 = Goblet("test")
        app2 = Goblet("test")

        @app1.route("/home")
        @app2.route("/home2")
        @app1.schedule("* * * * *")
        def dummy_function(self, home_id):
            return True

        @app2.schedule("1 * * * *")
        def dummy_function2(self, home_id):
            return True

        app1.combine(app2)

        assert list(app1.handlers["route"].resources.keys()) == ["/home", "/home2"]
        assert list(app1.handlers["schedule"].resources.keys()) == [
            "dummy_function",
            "dummy_function2",
        ]

    def test_is_http(self):

        app1 = Goblet("test1")
        app2 = Goblet("test2")
        app3 = Goblet("test3")

        @app1.schedule("1 * * * *")
        def dummy_function1(self):
            return True

        @app2.route("/home")
        def dummy_function2(self):
            return True

        @app3.topic("test")
        def dummy_function3(self):
            return True

        assert app1.is_http()
        assert app2.is_http()
        assert not app3.is_http()


    def test_before_request(self):
        app = Goblet("test")

        mock_request = Mock()
        mock_request.path = "/test"
        mock_request.method = "GET"


        @app.before_request()
        def before_request(request):
            request.custom_header = "test"
            return request
        
        @app.route("/test")
        def dummy_function():
            return app.current_request.custom_header
     
        assert  app(mock_request, {}) == "test"

    def test_after_request(self):
        app = Goblet("test")

        mock_request = Mock()
        mock_request.path = "/test"
        mock_request.method = "GET"


        @app.after_request()
        def after_request(response):
            return response + " after request"
        
        @app.route("/test")
        def dummy_function():
            return "test"
     
        assert app(mock_request, {}) == "test after request"
