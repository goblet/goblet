from unittest.mock import Mock
from goblet import Goblet
from goblet.handlers.uptime import Uptime
from goblet.test_utils import (
    mock_dummy_function,
    dummy_function,
)
from goblet.backends import CloudRun, CloudFunctionV1
from goblet_gcp_client import (
    get_responses,
    get_replay_count,
    reset_replay_count,
)


class TestUptime:
    def test_add_schedule(self, monkeypatch):
        app = Goblet(function_name="test-uptime")
        monkeypatch.setenv("GOOGLE_PROJECT", "TEST_PROJECT")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")

        app.uptime(timeout="30s")(dummy_function)

        uptime = app.handlers["uptime"]
        assert len(uptime.resources) == 1
        assert uptime.resources["dummy_function"]["func"] == dummy_function
        assert uptime.resources["dummy_function"]["kwargs"] == {"timeout": "30s"}

    def test_call_uptime(self, monkeypatch):
        app = Goblet(function_name="test-uptime")
        monkeypatch.setenv("GOOGLE_PROJECT", "TEST_PROJECT")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")

        mock = Mock()

        app.uptime()(mock_dummy_function(mock))

        headers = {
            "X-Goblet-Uptime-Name": "dummy_function",
        }

        mock_event = Mock()
        mock_event.headers = headers

        app(mock_event, None)

        assert mock.call_count == 1

    def test_deploy_uptime_cloudfunction(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "uptime-deploy")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        reset_replay_count()

        goblet_name = "uptime-test"
        uptime = Uptime(goblet_name, backend=CloudFunctionV1(Goblet()))
        uptime.register(
            "test",
            None,
            kwargs={"kwargs": {}},
        )

        uptime.deploy()

        responses = get_responses("uptime-deploy")

        assert get_replay_count() == 2

        assert responses[1]["body"]["monitoredResource"] == {
            "type": "uptime_url",
            "labels": {
                "host": "us-central1-goblet.cloudfunctions.net",
                "project_id": "goblet",
            },
        }
        assert responses[1]["body"]["httpCheck"] == {
            "useSsl": True,
            "path": "/uptime-test",
            "port": 443,
            "headers": {"X-Goblet-Uptime-Name": "test"},
            "requestMethod": "GET",
        }

    def test_deploy_uptime_cloudrun(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "uptime-deploy-cloudrun")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        reset_replay_count()

        goblet_name = "test-uptime"
        uptime = Uptime(goblet_name, backend=CloudRun(Goblet()))
        uptime.register(
            "cloudrun",
            None,
            kwargs={"kwargs": {}},
        )
        uptime.deploy()

        responses = get_responses("uptime-deploy-cloudrun")

        assert get_replay_count() == 2

        assert responses[1]["body"]["monitoredResource"] == {
            "type": "cloud_run_revision",
            "labels": {
                "project_id": "goblet",
                "revision_name": "",
                "location": "us-central1",
                "service_name": "test-uptime",
                "configuration_name": "",
            },
        }
        assert responses[1]["body"]["httpCheck"] == {
            "useSsl": True,
            "path": "/",
            "port": 443,
            "headers": {"X-Goblet-Uptime-Name": "cloudrun"},
            "requestMethod": "GET",
        }

    def test_destroy_uptime(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "uptime-destroy")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        reset_replay_count()

        goblet_name = "uptime-test"
        uptime = Uptime(goblet_name, backend=CloudFunctionV1(Goblet()))
        uptime.register(
            "test",
            None,
            kwargs={"kwargs": {}},
        )
        uptime.destroy()

        assert get_replay_count() == 2
