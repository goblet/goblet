from goblet import Goblet
from unittest.mock import Mock
from goblet.test_utils import mock_dummy_function


class TestHttp:
    def test_call_route(self):
        app = Goblet(function_name="goblet_example")
        mock = Mock()

        app.http()(mock_dummy_function(mock))

        mock_request = Mock()
        mock_request.path = "/"
        mock_request.headers = {}

        app(mock_request, None)

        assert mock.call_count == 1

    def test_call_headers_dict(self):
        app = Goblet(function_name="goblet_example")
        mock = Mock()

        @app.http(headers={"test": 1, "test2": 2})
        def mock_function(request):
            mock()
            return True

        mock_request = Mock()
        mock_request.path = "/"
        mock_request.headers = {"test": 1, "test2": 2}

        mock_request2 = Mock()
        mock_request2.path = "/"
        mock_request2.headers = {"test": 1}

        mock_request3 = Mock()
        mock_request3.path = "/"
        mock_request3.headers = {"test": 3}

        app(mock_request, None)
        app(mock_request2, None)
        app(mock_request3, None)

        assert mock.call_count == 1

    def test_call_headers_set(self):
        app = Goblet(function_name="goblet_example")
        mock = Mock()

        @app.http(headers={"test", "also_test"})
        def mock_function(request):
            mock()
            return True

        mock_request = Mock()
        mock_request.path = "/"
        mock_request.headers = {"test": 1, "also_test": 1}

        mock_request2 = Mock()
        mock_request2.path = "/"
        mock_request2.headers = {"test": 2}

        app(mock_request, None)
        app(mock_request2, None)

        assert mock.call_count == 1
