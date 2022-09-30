from goblet import Goblet
from goblet.infrastructures.redis import Redis
from goblet.test_utils import get_response, get_responses


class TestRedis:
    def test_add_redis(self):
        app = Goblet(function_name="goblet_example")

        app.redis(name="redis-test")
        redis = app.infrastructure["redis"]
        assert redis.resources["name"] == "redis-test"

    def test_deploy_redis(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "redis-deploy")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

        app = Goblet(function_name="goblet-example")
        app.redis(name="redis-test")

        app.deploy(
            force=True,
            skip_backend=True,
            skip_resources=True,
            config={
                "redis": {
                    "connectMode": "PRIVATE_SERVICE_ACCESS",
                    "authorizedNetwork": "projects/goblet/global/networks/default",
                }
            },
        )

        responses = get_responses("redis-deploy")
        assert len(responses) == 2
        assert responses[0]["body"]["response"]["tier"] == "BASIC"
        assert (
            responses[0]["body"]["response"]["connectMode"] == "PRIVATE_SERVICE_ACCESS"
        )
        assert "redis-test" in responses[0]["body"]["response"]["name"]

    # def test_update_redis(self, monkeypatch):
    #     monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
    #     monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
    #     monkeypatch.setenv("GOBLET_TEST_NAME", "redis-update")
    #     monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

    #     app = Goblet(function_name="goblet-example")
    #     app.redis(name="redis-test")

    #     app.deploy(
    #         force=True,
    #         skip_backend=True,
    #         skip_resources=True,
    #         config={
    #             "redis": {
    #                 "connectMode": "PRIVATE_SERVICE_ACCESS",
    #                 "authorizedNetwork": "projects/goblet/global/networks/default",
    #             }
    #         },
    #     )

    #     app.deploy(
    #         force=True,
    #         skip_backend=True,
    #         skip_resources=True,
    #         config={"redis": {"memorySizeGb": 2}},
    #     )

    #     updated_redis = get_response(
    #         "redis-update",
    #         "get-v1-projects-goblet-locations-us-central1-instances-redis-test_1.json",
    #     )
    #     assert "redis-test" in updated_redis["body"]["memorySizeGb"] == 2

    def test_destroy_redis(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "redis-destroy")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

        redis = Redis("goblet-redis", resources={"name": "redis-test"})
        redis.destroy()

        delete_redis = get_response(
            "redis-destroy",
            "delete-v1-projects-goblet-locations-us-central1-instances-redis-test_1.json",
        )
        assert "redis-test" in delete_redis["body"]["metadata"]["target"]

    # def test_deploy_redis_cloudrun(self, monkeypatch):
    #     monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
    #     monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
    #     monkeypatch.setenv("GOBLET_TEST_NAME", "redis-deploy-cloudrun")
    #     monkeypatch.setenv("GOBLET_HTTP_TEST", "RECORD")

    #     app = Goblet(function_name="goblet-example", backend="cloudrun")
    #     app.redis(name="redis-test-cloudrun")

    #     app.deploy(skip_resources=True)
