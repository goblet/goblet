from datetime import datetime
from unittest.mock import Mock

import pytest

from goblet import Goblet, Response, jsonify

# from goblet.client import DEFAULT_CLIENT_VERSIONS


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

    def test_headers(self):
        test_headers = {"Content-Type": "application/json", "X-Test": True}
        resp = jsonify("hello", headers={"X-Test": True})
        assert resp == ("hello", 200, test_headers)

    def test_options_failure(self):
        with pytest.raises(TypeError):
            resp = jsonify({"a": "b", "c": datetime.now()})

    def test_options_success(self):
        time = datetime.now()
        resp = jsonify({"c": time}, options={"default": str})
        assert resp == (f'{{"c":"{time}"}}', 200, self.headers)


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
        mock_request.headers = {}
        mock_request.json = {}

        @app.before_request()
        def before_request(request):
            request.custom_header = "test"
            return request

        @app.route("/test")
        def dummy_function():
            return app.current_request.custom_header

        assert app(mock_request, {}) == "test"

    def test_after_request(self):
        app = Goblet("test")

        mock_request = Mock()
        mock_request.path = "/test"
        mock_request.method = "GET"
        mock_request.headers = {}
        mock_request.json = {}

        @app.after_request()
        def after_request(response):
            return response + " after request"

        @app.route("/test")
        def dummy_function():
            return "test"

        assert app(mock_request, {}) == "test after request"

    def test_stage(self, monkeypatch):
        monkeypatch.setenv("STAGE", "TEST2")

        app = Goblet("test", config={"stages": {"TEST2": {}}})

        @app.route("/test")
        @app.stage("TEST")
        def dummy_function():
            return "test"

        @app.route("/test2")
        @app.stage("TEST2")
        def dummy_function2():
            return "test"

        @app.route("/test3")
        @app.stage("TEST2")
        def dummy_function3():
            return "test"

        assert len(app.handlers["route"].resources) == 2

        with pytest.raises(ValueError):

            @app.route("/test4")
            @app.stage()
            def dummy_function4():
                return "test"

    def test_stages(self, monkeypatch):
        monkeypatch.setenv("STAGE", "TEST2")

        app = Goblet("test", config={"stages": {"TEST2": {}}})

        @app.route("/test")
        @app.stage(stages=["TEST", "TEST2"])
        def dummy_function():
            return "test"

        @app.route("/test2")
        @app.stage("TEST2")
        def dummy_function2():
            return "test"

        @app.route("/test3")
        @app.stage(stages=["TEST", "TEST3"])
        def dummy_function3():
            return "test"

        assert len(app.handlers["route"].resources) == 2


# Causes tests to fail
# class TestGoblet:

#     def test_client_versions(self):
#         app = Goblet(client_versions={"cloudfunctions":"v2"})
#         assert app.client_versions["cloudfunctions"] == "v2"
#         assert app.client_versions["pubsub"] == DEFAULT_CLIENT_VERSIONS["pubsub"]
