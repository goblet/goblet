from goblet import Goblet
from goblet.deploy import Deployer
from goblet.test_utils import get_responses, dummy_function, get_response, mock_dummy_function

from unittest.mock import Mock


class TestPubSub:
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
        assert eventarc.resources[0]["topic"] == None
        assert eventarc.resources[0]["event_filters"] == [
            {"attribute": "type", "value": "google.cloud.storage.object.v1.finalized"},
            {"attribute": "bucket", "value": "BUCKET"},
        ]

    # def test_call_eventarc_topic(self):
    #     app = Goblet(function_name="goblet_example")
    #     mock = Mock()

    #     app.eventarc(topic="test")(mock_dummy_function(mock))

    #     request = Mock()
    #     request.headers={"Ce-Type": "google.cloud.pubsub.topic.v1.messagePublished", "Ce-Source": "//pubsub.googleapis.com/projects/goblet/topics/test"}
    #     mock_context.event_type = "providers/cloud.storage/eventTypes/bucket.finalize"
    #     event = {"bucket": "test"}

    #     app(request, None)
    #     assert mock.call_count == 1