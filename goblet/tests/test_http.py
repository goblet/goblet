from goblet import Goblet
from unittest.mock import Mock


class TestHttp():
    def test_call_route(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "TEST_PROJECT")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        app = Goblet(function_name="goblet_example")
        mock = Mock()

        @app.http()
        def mock_function(request):
            mock()
            return True

        mock_request = Mock()
        mock_request.path = '/'
        mock_request.headers = {}

        app(mock_request, None)

        assert(mock.call_count == 1)
