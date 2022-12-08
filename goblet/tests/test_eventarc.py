from goblet import Goblet
from goblet.resources.eventarc import EventArc
from goblet.test_utils import (
    get_responses,
    dummy_function,
    mock_dummy_function,
)
from goblet.backends.cloudrun import CloudRun

from unittest.mock import Mock


class TestEventArc:
    def test_add_trigger_topic(self):
        app = Goblet(function_name="goblet_example")

        app.eventarc(topic="test")(dummy_function)

        eventarc = app.handlers["eventarc"]
        assert len(eventarc.resources) == 1
        assert eventarc.resources[0]["func"] == dummy_function
        assert eventarc.resources[0]["topic"] == "test"
        assert eventarc.resources[0]["event_filters"] == [
            {
                "attribute": "type",
                "value": "google.cloud.pubsub.topic.v1.messagePublished",
            }
        ]

    def test_add_trigger_event_filter(self):
        app = Goblet(function_name="goblet_example")

        app.eventarc(
            event_filters=[
                {
                    "attribute": "type",
                    "value": "google.cloud.storage.object.v1.finalized",
                },
                {"attribute": "bucket", "value": "BUCKET"},
            ]
        )(dummy_function)

        eventarc = app.handlers["eventarc"]
        assert len(eventarc.resources) == 1
        assert eventarc.resources[0]["func"] == dummy_function
        assert eventarc.resources[0]["topic"] is None
        assert eventarc.resources[0]["event_filters"] == [
            {"attribute": "type", "value": "google.cloud.storage.object.v1.finalized"},
            {"attribute": "bucket", "value": "BUCKET"},
        ]

    def test_call_eventarc_topic(self):
        app = Goblet(function_name="goblet_example")
        mock = Mock()

        app.eventarc(topic="test")(mock_dummy_function(mock))

        request = Mock()
        request.path = "/x-goblet-eventarc-triggers/goblet-example-dummy-function"
        request.headers = {
            "Ce-Type": "google.cloud.pubsub.topic.v1.messagePublished",
            "Ce-Source": "//pubsub.googleapis.com/projects/goblet/topics/test",
        }

        app(request, None)
        assert mock.call_count == 1

    def test_call_eventarc_topic_no_response(self):
        app = Goblet(function_name="goblet_example")

        app.eventarc(topic="test")(mock_dummy_function(dummy_function))

        request = Mock()
        request.path = "/x-goblet-eventarc-triggers/goblet-example-dummy-function"
        request.headers = {
            "Ce-Type": "google.cloud.pubsub.topic.v1.messagePublished",
            "Ce-Source": "//pubsub.googleapis.com/projects/goblet/topics/test",
        }

        resp = app(request, None)
        assert resp.status_code == 200

    def test_sync_eventarc(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "eventarc-sync")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

        eventarc = EventArc(
            "test-eventarc",
            backend=CloudRun(Goblet(function_name="test-eventarc", backend="cloudrun")),
            resources=[
                {
                    "trigger_name": "test-eventarc-bucket-get",
                    "event_filters": [
                        {
                            "attribute": "type",
                            "value": "google.cloud.audit.log.v1.written",
                        },
                        {"attribute": "methodName", "value": "storage.objects.get"},
                        {"attribute": "serviceName", "value": "storage.googleapis.com"},
                    ],
                    "topic": None,
                    "region": "us-central1",
                    "name": "bucket_get",
                    "func": None,
                }
            ],
        )
        eventarc.sync(dryrun=True)
        eventarc.sync()

        responses = get_responses("eventarc-sync")

        assert len(responses) == 3
        assert responses[1] == responses[2]
        assert (
            "test-eventarc-bucket-get" not in responses[0]["body"]["metadata"]["target"]
        )

    def test_deploy_eventarc(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "eventarc-deploy")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

        eventarc = EventArc(
            "test-eventarc",
            backend=CloudRun(Goblet(function_name="test-eventarc", backend="cloudrun")),
            resources=[
                {
                    "trigger_name": "test-eventarc-bucket-get",
                    "event_filters": [
                        {
                            "attribute": "type",
                            "value": "google.cloud.audit.log.v1.written",
                        },
                        {"attribute": "methodName", "value": "storage.objects.delete"},
                        {"attribute": "serviceName", "value": "storage.googleapis.com"},
                    ],
                    "topic": None,
                    "region": "us-central1",
                    "name": "bucket_get",
                    "func": None,
                }
            ],
        )
        eventarc._deploy(
            config={
                "eventarc": {"serviceAccount": "test@goblet.iam.gserviceaccount.com"}
            }
        )

        responses = get_responses("eventarc-deploy")

        assert len(responses) == 1
        assert "test-eventarc-bucket-get" in responses[0]["body"]["metadata"]["target"]

    def test_update_eventarc(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "eventarc-update")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

        eventarc = EventArc(
            "test-eventarc",
            backend=CloudRun(Goblet(function_name="test-eventarc", backend="cloudrun")),
            resources=[
                {
                    "trigger_name": "test-eventarc-bucket-get",
                    "event_filters": [
                        {
                            "attribute": "type",
                            "value": "google.cloud.audit.log.v1.written",
                        },
                        {"attribute": "methodName", "value": "storage.objects.get"},
                        {"attribute": "serviceName", "value": "storage.googleapis.com"},
                    ],
                    "topic": None,
                    "region": "us-central1",
                    "name": "bucket_get",
                    "func": None,
                }
            ],
        )
        eventarc._deploy(
            config={
                "eventarc": {"serviceAccount": "test@goblet.iam.gserviceaccount.com"}
            }
        )

        responses = get_responses("eventarc-update")

        assert len(responses) == 2
        assert "test-eventarc-bucket-get" in responses[0]["body"]["metadata"]["target"]
        assert responses[1]["body"]["error"]["status"] == "ALREADY_EXISTS"

    def test_destroy_eventarc(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "eventarc-destroy")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

        eventarc = EventArc(
            "test-eventarc",
            backend=CloudRun(Goblet(function_name="test-eventarc", backend="cloudrun")),
            resources=[
                {
                    "trigger_name": "test-eventarc-bucket-get",
                    "event_filters": [
                        {
                            "attribute": "type",
                            "value": "google.cloud.audit.log.v1.written",
                        },
                        {"attribute": "methodName", "value": "storage.objects.get"},
                        {"attribute": "serviceName", "value": "storage.googleapis.com"},
                    ],
                    "topic": None,
                    "region": "us-central1",
                    "name": "bucket_get",
                    "func": None,
                }
            ],
        )
        eventarc.destroy()

        responses = get_responses("eventarc-destroy")

        assert len(responses) == 1
        assert "test-eventarc-bucket-get" in responses[0]["body"]["metadata"]["target"]
