import base64
from unittest.mock import Mock

import pytest

from goblet import Goblet, Response
from goblet.handlers.pubsub import PubSub
from goblet.test_utils import (
    dummy_function,
    mock_dummy_function,
)
from goblet.backends import CloudRun, CloudFunctionV1
from goblet_gcp_client import (
    get_responses,
    get_response,
    get_replay_count,
    reset_replay_count,
)


class TestPubSubSubscription:
    def test_add_topic(self):
        app = Goblet(function_name="goblet_example")

        app.pubsub_subscription("test")(dummy_function)

        pubsub = app.handlers["pubsub"]
        assert len(pubsub.resources) == 1
        assert (
            pubsub.resources["test"]["trigger"]["dummy_function"]["func"]
            == dummy_function
        )

    def test_add_topic_with_subscription(self):
        app = Goblet(function_name="goblet_example")

        app.pubsub_subscription("test", use_subscription="true")(dummy_function)

        pubsub = app.handlers["pubsub"]
        assert len(pubsub.resources) == 1
        assert (
            pubsub.resources["test"]["subscription"]["dummy_function"]["func"]
            == dummy_function
        )

    def test_add_topic_attributes(self):
        app = Goblet(function_name="goblet_example")

        app.pubsub_subscription("test", attributes={"test": True})(dummy_function)

        pubsub = app.handlers["pubsub"]
        assert len(pubsub.resources) == 1
        assert (
            pubsub.resources["test"]["trigger"]["dummy_function"]["func"]
            == dummy_function
        )
        assert pubsub.resources["test"]["trigger"]["dummy_function"]["attributes"] == {
            "test": True
        }
        assert (
            pubsub.resources["test"]["trigger"]["dummy_function"]["filter"]
            == 'attributes.test = "True"'
        )

    def test_add_topic_filter(self):
        app = Goblet(function_name="goblet_example")

        app.pubsub_subscription("test", filter='attributes.test = "1"')(dummy_function)

        pubsub = app.handlers["pubsub"]
        assert len(pubsub.resources) == 1
        assert (
            pubsub.resources["test"]["trigger"]["dummy_function"]["filter"]
            == 'attributes.test = "1"'
        )

    def test_call_topic(self):
        app = Goblet(function_name="goblet_example")

        @app.pubsub_subscription("test")
        def dummy_function(data):
            assert data == "test"

        mock_context = Mock()
        mock_context.resource = "projects/GOOGLE_PROJECT/topics/test"
        mock_context.event_type = "providers/cloud.pubsub/eventTypes/topic.publish"

        event = {"data": base64.b64encode("test".encode())}

        # assert dummy_function is run
        app(event, mock_context)

    def test_call_responses(self):
        app = Goblet(function_name="goblet_example")

        @app.pubsub_subscription("test")
        def dummy_function(data):
            return Response("500", status_code=500)

        @app.pubsub_subscription("test2")
        def dummy_function2(data):
            "no return"

        mock_context = Mock()
        mock_context.resource = "projects/GOOGLE_PROJECT/topics/test"
        mock_context.event_type = "providers/cloud.pubsub/eventTypes/topic.publish"

        event = {"data": base64.b64encode("test".encode())}

        mock_context2 = Mock()
        mock_context2.resource = "projects/GOOGLE_PROJECT/topics/test2"
        mock_context2.event_type = "providers/cloud.pubsub/eventTypes/topic.publish"

        assert app(event, mock_context).status_code == 500
        assert app(event, mock_context2) == "success"

    def test_call_topic_attributes(self):
        app = Goblet(function_name="goblet_example")

        @app.pubsub_subscription("test", attributes={"t": 1})
        def dummy_function(data):
            assert data == "test"

        @app.pubsub_subscription("test", attributes={"t": 3})
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
        app.pubsub_subscription("test")(mock_dummy_function(mock))

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

    def test_call_subscription_attributes(self):
        app = Goblet(function_name="goblet_example")

        mock = Mock()
        app.pubsub_subscription("test", attributes={"t": 1})(mock_dummy_function(mock))

        mock_request = Mock()
        mock_request.headers = {}
        event = {"data": base64.b64encode("test".encode()), "attributes": {"t": 1}}
        mock_request.json = {
            "message": event,
            "subscription": "projects/PROJECT/subscriptions/goblet_example-test",
        }
        mock_request.path = None

        app(mock_request, None)

        event2 = {"data": base64.b64encode("test".encode()), "attributes": {"t": 2}}
        mock_request.json = {
            "message": event2,
            "subscription": "projects/PROJECT/subscriptions/goblet_example-test",
        }
        app(mock_request, None)

        assert mock.call_count == 1

    def test_context(self):
        app = Goblet(function_name="goblet_example")

        @app.pubsub_subscription("test")
        def dummy_function(data):
            assert app.request_context.resource == "projects/GOOGLE_PROJECT/topics/test"

        mock_context = Mock()
        mock_context.resource = "projects/GOOGLE_PROJECT/topics/test"
        mock_context.event_type = "providers/cloud.pubsub/eventTypes/topic.publish"
        event = {"data": base64.b64encode("test".encode())}

        # assert dummy_function is run
        app(event, mock_context)

    def test_deploy_pubsub(self, monkeypatch, requests_mock):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "pubsub-deploy")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        requests_mock.register_uri("PUT", "https://storage.googleapis.com/mock")

        app = Goblet(function_name="goblet_topic")
        setattr(app, "entrypoint", "app")

        app.pubsub_subscription("test-topic")(dummy_function)

        app.deploy(force=True)

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

    def test_deploy_pubsub_cross_project(self, monkeypatch, requests_mock):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "pubsub-deploy-cross-project")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")
        service_account = "SERVICE_ACCOUNT@developer.gserviceaccount.com"

        requests_mock.register_uri("PUT", "https://storage.googleapis.com/mock")

        app = Goblet(
            function_name="goblet-topic-cross-project",
            config={"pubsub": {"serviceAccountEmail": service_account}},
        )
        setattr(app, "entrypoint", "app")

        app.pubsub_subscription("test", project="goblet-cross-project")(dummy_function)

        app.deploy(force=True)

        put_subscription = get_response(
            "pubsub-deploy-cross-project",
            "put-v1-projects-goblet-subscriptions-goblet-topic-cross-project-test_1.json",
        )
        responses = get_responses("pubsub-deploy-cross-project")
        assert "goblet-cross-project" in put_subscription["body"]["topic"]
        assert len(responses) == 6

    def test_deploy_pubsub_subscription_with_filter(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "pubsub-deploy-subscription-filter")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")
        service_account = "SERVICE_ACCOUNT@developer.gserviceaccount.com"

        app = Goblet(
            function_name="goblet-topic-subscription-filter",
            config={"pubsub": {"serviceAccountEmail": service_account}},
        )
        setattr(app, "entrypoint", "app")

        app.pubsub_subscription(
            "test", use_subscription=True, filter='attributes.test = "1"'
        )(dummy_function)

        app.deploy(force=True, skip_backend=True, skip_infra=True)

        put_subscription = get_response(
            "pubsub-deploy-subscription-filter",
            "put-v1-projects-goblet-subscriptions-goblet-topic-subscription-filter-test_1.json",
        )
        responses = get_responses("pubsub-deploy-subscription-filter")
        assert put_subscription["body"]["filter"] == 'attributes.test = "1"'
        assert len(responses) == 3

    def test_destroy_pubsub(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "pubsub-destroy")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        pubsub = PubSub(
            "goblet_topic",
            backend=CloudFunctionV1(Goblet()),
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
        monkeypatch.setenv("G_TEST_NAME", "pubsub-deploy-cloudrun")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        cloudrun_url = "https://goblet-12345.a.run.app"
        service_account = "SERVICE_ACCOUNT@developer.gserviceaccount.com"

        pubsub = PubSub(
            "goblet",
            backend=CloudRun(
                Goblet(
                    backend="cloudrun",
                    config={"pubsub": {"serviceAccountEmail": service_account}},
                )
            ),
        )
        pubsub.register("test", None, kwargs={"topic": "test", "kwargs": {}})

        pubsub._deploy()

        responses = get_responses("pubsub-deploy-cloudrun")

        assert len(responses) == 3
        assert responses[1]["body"]["status"]["url"] == cloudrun_url
        assert (
            responses[2]["body"]["pushConfig"]["oidcToken"]["serviceAccountEmail"]
            == service_account
        )
        assert (
            responses[2]["body"]["pushConfig"]["oidcToken"]["audience"] == cloudrun_url
        )
        assert responses[2]["body"]["pushConfig"]["pushEndpoint"] == cloudrun_url
        assert responses[2]["body"]["topic"] == "projects/goblet/topics/test"

    def test_destroy_pubsub_cloudrun(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "pubsub-destroy-cloudrun")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        pubsub = PubSub(
            "goblet",
            resources={"test": {"trigger": {}, "subscription": {"test": {}}}},
            backend=CloudRun(Goblet(backend="cloudrun")),
        )
        pubsub.destroy()

        responses = get_responses("pubsub-destroy-cloudrun")

        assert len(responses) == 1
        assert responses[0]["body"] == {}

    def test_update_pubsub_subscription(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "pubsub-update-subscription")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")
        reset_replay_count()

        new_service_account = "service_account_new@goblet.iam.gserviceaccount.com"

        pubsub = PubSub(
            "test-pubsub",
            backend=CloudFunctionV1(
                Goblet(config={"pubsub": {"serviceAccountEmail": new_service_account}})
            ),
        )
        pubsub.register(
            "test",
            None,
            kwargs={
                "topic": "test",
                "kwargs": {"project": "goblet", "use_subscription": "true"},
            },
        )

        pubsub._deploy()

        responses = get_responses("pubsub-update-subscription")

        assert get_replay_count() == 2
        assert (
            responses[1]["body"]["pushConfig"]["oidcToken"]["serviceAccountEmail"]
            == new_service_account
        )

    def test_update_pubsub_subscription_force_update_false(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv(
            "G_TEST_NAME", "pubsub-update-subscription-force-update-false"
        )
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        service_account = "SERVICE_ACCOUNT@developer.gserviceaccount.com"

        pubsub = PubSub(
            "test-cross-project",
            backend=CloudFunctionV1(
                Goblet(config={"pubsub": {"serviceAccountEmail": service_account}})
            ),
        )
        pubsub.register(
            "test",
            None,
            kwargs={"topic": "test", "kwargs": {"project": "goblet_cross_project"}},
        )

        pubsub._deploy()

        responses = get_responses("pubsub-update-subscription-force-update-false")

        assert len(responses) == 1
        assert responses[0]["body"]["topic"] != "goblet_cross_project"

    def test_update_pubsub_subscription_force_update_true(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv(
            "G_TEST_NAME", "pubsub-update-subscription-force-update-true"
        )
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        reset_replay_count()

        service_account = "SERVICE_ACCOUNT@developer.gserviceaccount.com"

        pubsub = PubSub(
            "test-cross-project",
            backend=CloudFunctionV1(
                Goblet(config={"pubsub": {"serviceAccountEmail": service_account}})
            ),
        )
        pubsub.register(
            "test",
            None,
            kwargs={
                "topic": "test",
                "kwargs": {"project": "goblet_cross_project", "force_update": True},
            },
        )

        pubsub._deploy()

        responses = get_responses("pubsub-update-subscription-force-update-true")
        replay_count = get_replay_count()
        assert replay_count == 3
        assert responses[1]["body"]["topic"] != "goblet_cross_project"

    def test_sync_pubsub_cloudrun(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "pubsub-sync-cloudrun")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        pubsub = PubSub("goblet", backend=CloudRun(Goblet(backend="cloudrun")))
        pubsub.sync(dryrun=True)
        pubsub.sync()

        responses = get_responses("pubsub-sync-cloudrun")

        assert len(responses) == 3
        assert responses[1] == responses[2]
        assert responses[0]["body"] == {}

    def test_deploy_pubsub_subscription_with_config(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "pubsub-deploy-subscription-config")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")
        service_account = "SERVICE_ACCOUNT@developer.gserviceaccount.com"

        app = Goblet(
            function_name="goblet-topic-subscription-config",
            config={"pubsub": {"serviceAccountEmail": service_account}},
        )
        setattr(app, "entrypoint", "app")

        app.pubsub_subscription(
            "test", use_subscription=True, config={"enableExactlyOnceDelivery": True}
        )(dummy_function)

        app.deploy(force=True, skip_backend=True, skip_infra=True)

        put_subscription = get_response(
            "pubsub-deploy-subscription-config",
            "put-v1-projects-goblet-subscriptions-goblet-topic-subscription-config-test_1.json",
        )
        responses = get_responses("pubsub-deploy-subscription-config")
        assert put_subscription["body"]["enableExactlyOnceDelivery"]
        assert len(responses) == 3
