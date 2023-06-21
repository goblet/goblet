from goblet import Goblet
from goblet_gcp_client import get_response
from goblet.infrastructures.pubsub import PubSubClient


class TestPubSub:
    def test_add_pubsub_topics(self):
        app = Goblet(function_name="goblet_example")

        app.pubsub_topic(name="pubsub_topic01")
        app.pubsub_topic(name="pubsub_topic02")

        pubsub_topic = app.infrastructure["pubsub_topic"]
        assert pubsub_topic.resource["pubsub_topic01"]["id"] == "pubsub_topic01"
        assert pubsub_topic.resource["pubsub_topic02"]["id"] == "pubsub_topic02"

    def test_create_pubsub_topic(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "pubsub-deploy")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        app = Goblet(function_name="goblet_example")

        client: PubSubClient = app.pubsub_topic(name="test")  # noqa: F841

        app.deploy(
            force=True,
            skip_backend=True,
        )

        put_pubsub_topic = get_response(
            "pubsub-deploy",
            "put-v1-projects-test_project-topics-test_1.json",
        )

        assert put_pubsub_topic["body"]["name"] == "projects/goblet/topics/test"
    def test_destroy_pubsub_topic(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "pubsub-deploy")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        app = Goblet(function_name="goblet_example")

        client: PubSubClient = app.pubsub_topic(name="test")  # noqa: F841

        app.destroy(
            skip_backend=True,
        )

        delete_pubsub_topic = get_response(
            "pubsub-deploy",
            "delete-v1-projects-test_project-topics-test_1.json",
        )

        assert delete_pubsub_topic["body"] == {}
