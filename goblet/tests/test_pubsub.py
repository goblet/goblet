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
            "put-v1-projects-goblet-topics-test_1.json",
        )

        pubsub_topic = app.infrastructure["pubsub_topic"]

        assert put_pubsub_topic["body"]["name"] == "projects/goblet/topics/test"
        assert pubsub_topic.resource["test"]["id"] == "test"

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
            "delete-v1-projects-goblet-topics-test_1.json",
        )

        pubsub_topic = app.infrastructure["pubsub_topic"]

        assert delete_pubsub_topic["body"] == {}
        assert pubsub_topic.resource["test"]["id"] == "test"

    def test_update_pubsub_topic(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "pubsub-update")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        app = Goblet(function_name="goblet_example")

        app.pubsub_topic(name="test")  # noqa: F841

        app.deploy(
            force=True,
            skip_backend=True,
        )

        put_pubsub_topic = get_response(
            "pubsub-update",
            "put-v1-projects-goblet-topics-test_1.json",
        )
        pubsub_topic = app.infrastructure["pubsub_topic"]

        assert put_pubsub_topic["body"]["name"] == "projects/goblet/topics/test"
        assert "messageRetentionDuration" not in put_pubsub_topic["body"]
        assert pubsub_topic.resource["test"]["id"] == "test"
        assert pubsub_topic.resource["test"]["config"] is None

        app.pubsub_topic(name="test", config={"messageRetentionDuration": "3600s"})

        app.deploy(
            force=True,
            skip_backend=True,
        )

        patch_pubsub_topic = get_response(
            "pubsub-update",
            "patch-v1-projects-goblet-topics-test_1.json",
        )
        pubsub_topic = app.infrastructure["pubsub_topic"]

        assert patch_pubsub_topic["body"]["name"] == "projects/goblet/topics/test"
        assert (
            "messageRetentionDuration" in patch_pubsub_topic["body"]
            and patch_pubsub_topic["body"]["messageRetentionDuration"] == "3600s"
        )
        assert pubsub_topic.resource["test"]["id"] == "test"
        assert pubsub_topic.resource["test"]["config"] == {
            "messageRetentionDuration": "3600s"
        }
