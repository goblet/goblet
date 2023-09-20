from goblet import Goblet, goblet_entrypoint
from goblet.handlers.storage import Storage
from goblet_gcp_client import get_responses
from goblet.test_utils import dummy_function, mock_dummy_function
from goblet.backends import CloudFunctionV1
from unittest.mock import Mock
import pytest


class TestStorage:
    def test_add_bucket(self, monkeypatch):
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        app = Goblet(function_name="goblet_example")

        app.storage("test", "finalize")(dummy_function)
        app.storage("test2", "archive")(dummy_function)

        storage = app.handlers["storage"]
        assert len(storage.resources) == 2
        assert storage.resources[0]["event_type"] == "finalize"
        assert storage.resources[1]["event_type"] == "archive"

    def test_add_invalid_event(self):
        app = Goblet(function_name="goblet_example")

        with pytest.raises(Exception):
            app.storage("test", "wrong")(dummy_function)

    def test_call_storage(self, monkeypatch):
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        app = Goblet(function_name="goblet_example")
        mock = Mock()

        app.storage("test", "finalize")(mock_dummy_function(mock))

        mock_context = Mock()
        mock_context.event_type = "providers/cloud.storage/eventTypes/bucket.finalize"
        event = {"bucket": "test"}

        app(event, mock_context)
        assert mock.call_count == 1

    def test_deploy_storage(self, monkeypatch, requests_mock):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "storage-deploy")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        requests_mock.register_uri("PUT", "https://storage.googleapis.com/mock")

        app = Goblet(function_name="goblet_storage")
        setattr(app, "entrypoint", "app")

        app.storage("test", "finalize")(dummy_function)

        app.deploy(force=True)

        responses = get_responses("storage-deploy")

        assert len(responses) == 3
        assert responses[2]["body"]["metadata"]["target"].endswith(
            "goblet_storage-storage-test-finalize"
        )
        assert (
            responses[2]["body"]["metadata"]["request"]["eventTrigger"]["resource"]
            == "projects/goblet/buckets/test"
        )
        assert (
            responses[2]["body"]["metadata"]["request"]["eventTrigger"]["eventType"]
            == "google.storage.object.finalize"
        )

    def test_destroy_storage(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "storage-destroy")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        storage = Storage(
            "goblet_storage",
            resources=[{"bucket": "test", "event_type": "finalize", "name": "test"}],
            backend=CloudFunctionV1(Goblet(backend="cloudrun")),
        )
        storage.destroy()

        responses = get_responses("storage-destroy")

        assert len(responses) == 1
        assert responses[0]["body"]["metadata"]["type"] == "DELETE_FUNCTION"
        assert responses[0]["body"]["metadata"]["target"].endswith(
            "goblet_storage-storage-test-finalize"
        )

    def test_deploy_storage_cloudfunction_v2(self, monkeypatch, requests_mock):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "storage-deploy-cloudfunctionv2")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        requests_mock.register_uri("PUT", "https://storage.googleapis.com/mock")
        requests_mock.register_uri("POST", "https://oauth2.googleapis.com/token")

        def storage(event):
            app.log.info(event)

        app = Goblet(
            function_name="storage-deploy-cloudfunctionv2",
            backend="cloudfunctionv2",
            config={
                "runtime": "python38",
                "cloudfunction_v2": {
                    "eventTrigger": {
                        "serviceAccountEmail": "goblet@goblet.iam.gserviceaccount.com"
                    },
                },
            },
        )
        goblet_entrypoint(app)

        app.storage("storage-deploy-cloudfunctionv2", "finalized")(storage)
        app.deploy(force=True)

        responses = get_responses("storage-deploy-cloudfunctionv2")
        assert len(responses) == 3
        assert responses[0]["body"]["metadata"]["target"].endswith(
            "storage-deploy-cloudfunctionv2-storage-storage-finalized"
        )
        assert (
            responses[0]["body"]["response"]["eventTrigger"]["eventFilters"][0]["value"]
            == "storage-deploy-cloudfunctionv2"
        )
        assert (
            responses[0]["body"]["response"]["eventTrigger"]["eventType"]
            == "google.cloud.storage.object.v1.finalized"
        )
