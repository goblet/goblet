from goblet import Goblet
from goblet.infrastructures.redis import Redis
from goblet.test_utils import dummy_function
from goblet_gcp_client import get_response, get_responses, reset_replay_count, get_replay_count


class TestRedis:
    def test_add_redis(self):
        app = Goblet(function_name="goblet_example")

        app.redis(name="redis-test")
        redis = app.infrastructure["redis"]
        assert redis.resource["name"] == "redis-test"

    def test_deploy_redis(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "redis-deploy")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        app = Goblet(
            function_name="goblet-example",
            config={
                "redis": {
                    "connectMode": "PRIVATE_SERVICE_ACCESS",
                    "authorizedNetwork": "projects/goblet/global/networks/default",
                }
            },
        )
        app.redis(name="redis-test")

        app.deploy(force=True, skip_backend=True, skip_resources=True)

        post_redis = get_response(
            "redis-deploy",
            "get-v1-projects-goblet-locations-us-central1-instances-redis-test_1.json",
        )

        assert (
            post_redis["body"]["authorizedNetwork"]
            == "projects/goblet/global/networks/default"
        )
        assert post_redis["body"]["tier"] == "BASIC"
        assert post_redis["body"]["connectMode"] == "PRIVATE_SERVICE_ACCESS"

    def test_update_redis(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "redis-update")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        reset_replay_count()

        app = Goblet(function_name="goblet-example",
            config={"redis": {"memorySizeGb": 2}})
        app.redis(name="redis-test")

        app.deploy(
            force=True,
            skip_backend=True,
            skip_resources=True
        )
        
        redis_response = get_response(
            "redis-update",
            "get-v1-projects-goblet-locations-us-central1-instances-redis-test_1.json",
        )
        assert redis_response["body"]["memorySizeGb"] == 2
        assert get_replay_count() == 5

    def test_destroy_redis(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "redis-destroy")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        redis = Redis("goblet-redis", resource={"name": "redis-test"})
        redis.destroy()

        delete_redis = get_response(
            "redis-destroy",
            "delete-v1-projects-goblet-locations-us-central1-instances-redis-test_1.json",
        )
        assert "redis-test" in delete_redis["body"]["metadata"]["target"]

    def test_deploy_cloudrun(self, monkeypatch, requests_mock):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "redis-deploy-cloudrun")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        requests_mock.register_uri(
            "HEAD",
            "https://storage.googleapis.com/mock",
            headers={"x-goog-hash": "crc32c=+kjoHA==, md5=QcWxCkEOHzBSBgerQcjMEg=="},
        )
        requests_mock.register_uri("PUT", "https://storage.googleapis.com/mock")

        app = Goblet(
            function_name="goblet-example",
            backend="cloudrun",
            config={
                "redis": {
                    "connectMode": "PRIVATE_SERVICE_ACCESS",
                    "authorizedNetwork": "projects/goblet/global/networks/default",
                }
            },
        )
        app.redis(name="redis-test")

        app.handlers["http"].register("", dummy_function, {})

        app.deploy(skip_resources=True, skip_infra=True)
        app.destroy(skip_infra=True)

        cloudrun_response = get_response(
            "redis-deploy-cloudrun",
            "get-v2-projects-goblet-locations-us-central1-operations-a6538a4e-5074-43bb-9e27-86da04379645_1.json",
        )["body"]["response"]
        redis_response = get_response(
            "redis-deploy-cloudrun",
            "get-v1-projects-goblet-locations-us-central1-instances-redis-test_1.json",
        )["body"]

        env_vars = cloudrun_response["template"]["containers"][0]["env"]

        assert env_vars[0]["name"] == "REDIS_INSTANCE_NAME"
        assert env_vars[0]["value"] == redis_response["name"]
        assert env_vars[1]["name"] == "REDIS_HOST"
        assert env_vars[1]["value"] == redis_response["host"]
        assert env_vars[2]["name"] == "REDIS_PORT"
        assert env_vars[2]["value"] == str(redis_response["port"])

    def test_deploy_cloudfunction(self, monkeypatch, requests_mock):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "redis-deploy-function")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        requests_mock.register_uri(
            "HEAD",
            "https://storage.googleapis.com/mock",
            headers={"x-goog-hash": "crc32c=+kjoHA==, md5=QcWxCkEOHzBSBgerQcjMEg=="},
        )
        requests_mock.register_uri("PUT", "https://storage.googleapis.com/mock")

        app = Goblet(
            function_name="goblet-example",
            backend="cloudfunction",
            config={
                "redis": {
                    "connectMode": "PRIVATE_SERVICE_ACCESS",
                    "authorizedNetwork": "projects/goblet/global/networks/default",
                }
            },
        )
        app.redis(name="redis-test")

        app.handlers["http"].register("", dummy_function, {})

        app.deploy(
            skip_resources=True,
            skip_infra=True,
        )
        app.destroy(skip_infra=True)

        responses = get_responses("redis-deploy-function")
        function_response = responses[6]["body"]["metadata"]
        redis_response = responses[3]["body"]

        env_vars = function_response["request"]["environmentVariables"]
        assert redis_response["host"] == env_vars["REDIS_HOST"]
        assert redis_response["port"] == int(env_vars["REDIS_PORT"])
        assert redis_response["name"] == env_vars["REDIS_INSTANCE_NAME"]

    def test_deploy_cloudfunctionv2(self, monkeypatch, requests_mock):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "redis-deploy-functionv2")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        requests_mock.register_uri(
            "HEAD",
            "https://storage.googleapis.com/mock",
            headers={"x-goog-hash": "crc32c=+kjoHA==, md5=QcWxCkEOHzBSBgerQcjMEg=="},
        )
        requests_mock.register_uri("PUT", "https://storage.googleapis.com/mock")

        app = Goblet(
            function_name="goblet-example",
            backend="cloudfunctionv2",
            config={
                "runtime": "python38",
                "redis": {
                    "connectMode": "PRIVATE_SERVICE_ACCESS",
                    "authorizedNetwork": "projects/goblet/global/networks/default",
                },
            },
        )
        app.redis(name="redis-test")
        app.handlers["http"].register("", dummy_function, {})

        app.deploy(skip_resources=True, skip_infra=True)
        app.destroy(skip_infra=True)

        responses = get_responses("redis-deploy-functionv2")
        functionv2_response = responses[3]["body"]["response"]
        redis_response = responses[1]["body"]

        env_vars = functionv2_response["serviceConfig"]["environmentVariables"]

        assert redis_response["host"] == env_vars["REDIS_HOST"]
        assert redis_response["port"] == int(env_vars["REDIS_PORT"])
        assert redis_response["name"] == env_vars["REDIS_INSTANCE_NAME"]
