from goblet import Goblet
from goblet.deploy import Deployer
from goblet.resources.pubsub import PubSub
from goblet.test_utils import (
    get_responses,
    dummy_function,
    get_response,
    mock_dummy_function,
)

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

    def test_add_topic_with_subscription(self):
        app = Goblet(function_name="goblet_example")

        app.topic("test", use_subscription="true")(dummy_function)

        pubsub = app.handlers["pubsub"]
        assert len(pubsub.resources) == 1
        assert (
            pubsub.resources["test"]["subscription"]["dummy_function"]["func"]
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

    def test_call_subscription(self):
        app = Goblet(function_name="goblet_example")

        mock = Mock()
        app.topic("test")(mock_dummy_function(mock))

        mock_request = Mock()
        mock_request.headers = {}
        event = {"data": base64.b64encode("test".encode())}
        mock_request.json = {
            "message": event,
            "subscription": "projects/PROJECT/subscriptions/goblet_example-test",
        }
        mock_request.path = None

        # assert dummy_function is run
        app(mock_request, None)
        assert mock.call_count == 1

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

    def test_deploy_pubsub_cross_project(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "pubsub-deploy-cross-project")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")
        service_account = "SERVICE_ACCOUNT@developer.gserviceaccount.com"

        app = Goblet(function_name="goblet-topic-cross-project")
        setattr(app, "entrypoint", "app")

        app.topic("test", project="goblet-cross-project")(dummy_function)

        Deployer({"name": app.function_name}).deploy(
            app, force=True, config={"pubsub": {"serviceAccountEmail": service_account}}
        )

        put_subscription = get_response(
            "pubsub-deploy-cross-project",
            "put-v1-projects-goblet-subscriptions-goblet-topic-cross-project-test_1.json",
        )
        responses = get_responses("pubsub-deploy-cross-project")
        assert "goblet-cross-project" in put_subscription["body"]["topic"]
        assert len(responses) == 5

    def test_destroy_pubsub(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "pubsub-destroy")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

        pubsub = PubSub(
            "goblet_topic",
            resources={
                "test-topic": {"trigger": {"test-topic": {}}, "subscription": {}}
            },
        )
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

        pubsub = PubSub(
            "goblet",
            resources={"test": {"trigger": {}, "subscription": {"test": {}}}},
            backend="cloudrun",
        )
        pubsub.destroy()

        responses = get_responses("pubsub-destroy-cloudrun")

        assert len(responses) == 1
        assert responses[0]["body"] == {}

    def test_update_pubsub_subscription(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "pubsub-update-subscription")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

        pubsub = PubSub("test-cross-project")
        pubsub.register_topic(
            "test",
            None,
            kwargs={"topic": "test", "kwargs": {"project": "goblet-cross-project"}},
        )

        new_service_account = "service_account_new@goblet.iam.gserviceaccount.com"
        pubsub._deploy(config={"pubsub": {"serviceAccountEmail": new_service_account}})

        responses = get_responses("pubsub-update-subscription")

        assert len(responses) == 3
        assert (
            responses[1]["body"]["pushConfig"]["oidcToken"]["serviceAccountEmail"]
            == new_service_account
        )
        assert responses[2]["body"]["error"]["code"] == 409

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
