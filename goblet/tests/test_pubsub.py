from goblet import Goblet
from goblet.deploy import Deployer
from goblet.resources.pubsub import PubSub
from goblet.test_utils import get_responses, dummy_function

from unittest.mock import Mock
import base64
import pytest


class TestPubSub:
    def test_add_topic(self):
        app = Goblet(function_name="goblet_example")

        app.topic("test")(dummy_function)

        pubsub = app.handlers["pubsub"]
        assert len(pubsub.resources) == 1
        assert (
            pubsub.resources["test"]["trigger"]["dummy_function"]["func"]
            == dummy_function
        )

    def test_add_topic_attributes(self):
        app = Goblet(function_name="goblet_example")

        app.topic("test", attributes={"test": True})(dummy_function)

        pubsub = app.handlers["pubsub"]
        assert len(pubsub.resources) == 1
        assert (
            pubsub.resources["test"]["trigger"]["dummy_function"]["func"]
            == dummy_function
        )
        assert pubsub.resources["test"]["trigger"]["dummy_function"]["attributes"] == {
            "test": True
        }

    def test_call_topic(self):
        app = Goblet(function_name="goblet_example")

        @app.topic("test")
        def dummy_function(data):
            assert data == "test"

        mock_context = Mock()
        mock_context.resource = "projects/GOOGLE_PROJECT/topics/test"
        mock_context.event_type = "providers/cloud.pubsub/eventTypes/topic.publish"

        event = {"data": base64.b64encode("test".encode())}

        # assert dummy_function is run
        app(event, mock_context)

    def test_call_topic_attributes(self):
        app = Goblet(function_name="goblet_example")

        @app.topic("test", attributes={"t": 1})
        def dummy_function(data):
            assert data == "test"

        @app.topic("test", attributes={"t": 3})
        def dummy_function2(data):
            raise Exception()

        mock_context = Mock()
        mock_context.resource = "projects/GOOGLE_PROJECT/topics/test"
        mock_context.event_type = "providers/cloud.pubsub/eventTypes/topic.publish"

        event = {"data": base64.b64encode("test".encode()), "attributes": {"t": 1}}
        event2 = {"data": base64.b64encode("test2".encode()), "attributes": {"t": 2}}
        event3 = {"data": base64.b64encode("test3".encode()), "attributes": {"t": 3}}

        # assert dummy_function is run
        app(event, mock_context)
        app(event2, mock_context)
        # assert dummy function2 is run
        with pytest.raises(Exception):
            app(event3, mock_context)

    def test_context(self):
        app = Goblet(function_name="goblet_example")

        @app.topic("test")
        def dummy_function(data):
            assert app.request_context.resource == "projects/GOOGLE_PROJECT/topics/test"

        mock_context = Mock()
        mock_context.resource = "projects/GOOGLE_PROJECT/topics/test"
        mock_context.event_type = "providers/cloud.pubsub/eventTypes/topic.publish"
        event = {"data": base64.b64encode("test".encode())}

        # assert dummy_function is run
        app(event, mock_context)

    def test_deploy_pubsub(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "pubsub-deploy")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

        app = Goblet(function_name="goblet_topic")
        setattr(app, "entrypoint", "app")

        app.topic("test-topic")(dummy_function)

        Deployer().deploy(app, force=True)

        responses = get_responses("pubsub-deploy")

        assert len(responses) == 3
        assert responses[2]["body"]["metadata"]["target"].endswith(
            "goblet_topic-topic-test-topic"
        )
        assert (
            responses[2]["body"]["metadata"]["request"]["eventTrigger"]["resource"]
            == "projects/goblet/topics/test-topic"
        )
        assert (
            responses[2]["body"]["metadata"]["request"]["eventTrigger"]["eventType"]
            == "providers/cloud.pubsub/eventTypes/topic.publish"
        )

    def test_destroy_pubsub(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "pubsub-destroy")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

        pubsub = PubSub("goblet_topic", resources={"test-topic": {}})
        pubsub.destroy()

        responses = get_responses("pubsub-destroy")

        assert len(responses) == 1
        assert responses[0]["body"]["metadata"]["type"] == "DELETE_FUNCTION"
        assert responses[0]["body"]["metadata"]["target"].endswith(
            "goblet_topic-topic-test-topic"
        )

    def test_deploy_pubsub_cloudrun(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "pubsub-deploy-cloudrun")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

        pubsub = PubSub("goblet", backend="cloudrun")
        pubsub.register_topic("test", None, kwargs={"topic": "test", "kwargs": {}})

        cloudrun_url = "https://goblet-12345.a.run.app"
        service_account = "SERVICE_ACCOUNT@developer.gserviceaccount.com"

        pubsub._deploy(config={"pubsub": {"serviceAccountEmail": service_account}})

        responses = get_responses("pubsub-deploy-cloudrun")

        assert len(responses) == 2
        assert responses[0]["body"]["status"]["url"] == cloudrun_url
        assert (
            responses[1]["body"]["pushConfig"]["oidcToken"]["serviceAccountEmail"]
            == service_account
        )
        assert (
            responses[1]["body"]["pushConfig"]["oidcToken"]["audience"] == cloudrun_url
        )
        assert responses[1]["body"]["pushConfig"]["pushEndpoint"] == cloudrun_url
        assert responses[1]["body"]["topic"] == "projects/goblet/topics/test"

    def test_destroy_pubsub_cloudrun(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "pubsub-destroy-cloudrun")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

        pubsub = PubSub("goblet", resources={"test": {}}, backend="cloudrun")
        pubsub.destroy()

        responses = get_responses("pubsub-destroy-cloudrun")

        assert len(responses) == 1
        assert responses[0]["body"] == {}

    def test_sync_pubsub_cloudrun(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "pubsub-sync-cloudrun")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

        pubsub = PubSub("goblet", backend="cloudrun")
        pubsub.sync(dryrun=True)
        pubsub.sync()

        responses = get_responses("pubsub-sync-cloudrun")

        assert len(responses) == 3
        assert responses[1] == responses[2]
        assert responses[0]["body"] == {}
