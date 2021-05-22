from goblet import Goblet
from unittest.mock import Mock
from goblet.test_utils import mock_dummy_function


class TestHttp():
    def test_call_route(self):
        app = Goblet(function_name="goblet_example")
        mock = Mock()

        app.http()(mock_dummy_function(mock))

        mock_request = Mock()
        mock_request.path = '/'
        mock_request.headers = {}

        app(mock_request, None)

        assert(mock.call_count == 1)
