from goblet import Goblet, goblet_entrypoint
from goblet.handlers.http import HTTP
from goblet_gcp_client import (
    get_responses,
    get_response,
    get_replay_count,
    reset_replay_count,
)
from goblet.test_utils import dummy_function, DATA_DIR_MAIN
from goblet.errors import GobletError
import pytest


class TestDeployer:
    def test_deploy_http_function(self, monkeypatch, requests_mock):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "deployer-function-deploy")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        requests_mock.register_uri("PUT", "https://storage.googleapis.com/mock")

        app = Goblet(function_name="goblet_example")
        setattr(app, "entrypoint", "app")

        app.handlers["http"] = HTTP("name", app)

        app.deploy(skip_handlers=True, skip_infra=True, force=True)

        responses = get_responses("deployer-function-deploy")
        assert len(responses) == 3

    def test_deploy_http_function_v2(self, monkeypatch, requests_mock):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "deployer-function-deploy-v2")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        requests_mock.register_uri("PUT", "https://storage.googleapis.com/mock")

        app = Goblet(
            function_name="goblet-test-http-v2",
            backend="cloudfunctionv2",
            config={"runtime": "python38"},
        )
        setattr(app, "entrypoint", "app")

        app.handlers["http"].register("", dummy_function, {})

        app.deploy(skip_handlers=True, skip_infra=True, force=True)

        responses = get_responses("deployer-function-deploy-v2")
        assert len(responses) == 3

    def test_deploy_cloudrun(self, monkeypatch, requests_mock):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "deployer-cloudrun-deploy")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        requests_mock.register_uri("PUT", "https://storage.googleapis.com/mock")

        app = Goblet(
            function_name="goblet",
            backend="cloudrun",
            config={
                "cloudrun_revision": {
                    "serviceAccount": "test-746@goblet.iam.gserviceaccount.com"
                }
            },
        )
        setattr(app, "entrypoint", "app")

        app.handlers["http"] = HTTP("name", app)

        app.deploy(skip_handlers=True, skip_infra=True, force=True)

        responses = get_responses("deployer-cloudrun-deploy")
        assert len(responses) == 10

    def test_deploy_cloudrun_multi_container(self, monkeypatch, requests_mock):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "deployer-cloudrun-deploy-multi-container")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        requests_mock.register_uri("PUT", "https://storage.googleapis.com/mock")
        reset_replay_count()

        app = Goblet(
            function_name="multi-container",
            backend="cloudrun",
            routes_type="cloudrun",
            config={
                "cloudrun": {"launchStage": "BETA"},
                "deploy": {"environmentVariables": {"PORT": "80"}},
                "cloudrun_container": {
                    "env": [{"name": "PORT", "value": "80"}],
                    "ports": [],
                },
                "cloudrun_container_extra": [
                    {
                        "name": "nginx",
                        "image": "nginx:1.20.0-alpine",
                        "volumeMounts": [{"mountPath": "/etc/nginx/", "name": "nginx"}],
                        "ports": [{"containerPort": 8080}],
                    }
                ],
                "cloudrun_revision": {
                    "serviceAccount": "test@goblet.iam.gserviceaccount.com",
                    "volumes": [
                        {
                            "name": "nginx",
                            "secret": {
                                "secret": "nginx",
                                "items": [{"version": "latest", "path": "nginx.conf"}],
                            },
                        }
                    ],
                },
            },
        )
        setattr(app, "entrypoint", "app")

        app.handlers["http"] = HTTP("name", app, resources=[{"http": True}])

        app.deploy(skip_handlers=True, skip_infra=True, force=True)

        service = get_response(
            "deployer-cloudrun-deploy-multi-container",
            "post-v2-projects-goblet-locations-us-central1-services_1.json",
        )

        assert get_replay_count() == 9
        assert len(service["body"]["metadata"]["template"]["containers"]) == 2
        assert (
            service["body"]["metadata"]["template"]["containers"][1]["name"] == "nginx"
        )

    def test_deploy_cloudrun_build_failed(self, monkeypatch, requests_mock):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "deployer-cloudrun-deploy-build-failed")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        requests_mock.register_uri("PUT", "https://storage.googleapis.com/mock")

        app = Goblet(
            function_name="goblet",
            backend="cloudrun",
            config={
                "cloudrun_revision": {
                    "serviceAccount": "test-746@goblet.iam.gserviceaccount.com"
                }
            },
        )
        setattr(app, "entrypoint", "app")

        app.handlers["http"] = HTTP("name", app)
        with pytest.raises(GobletError):
            app.deploy(skip_handlers=True, skip_infra=True, force=True)

    def test_destroy_cloudrun(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "deployer-cloudrun-destroy")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        app = Goblet(function_name="goblet", backend="cloudrun")

        app.destroy()

        responses = get_responses("deployer-cloudrun-destroy")
        assert len(responses) == 1
        assert responses[0]["body"]["status"] == "Success"
        assert responses[0]["body"]["details"]["name"] == "goblet"

    def test_destroy_http_function(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "deployer-function-destroy")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        app = Goblet(function_name="goblet_test_app")

        app.destroy()

        responses = get_responses("deployer-function-destroy")
        assert len(responses) == 1
        assert responses[0]["body"]["metadata"]["type"] == "DELETE_FUNCTION"
        assert (
            responses[0]["body"]["metadata"]["target"]
            == "projects/goblet/locations/us-central1/functions/goblet_test_app"
        )

    def test_destroy_http_function_all(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "deployer-function-destroy-all")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        app = Goblet(function_name="goblet_example")

        app.destroy(all=True)

        responses = get_responses("deployer-function-destroy-all")
        assert len(responses) == 4

    def test_set_iam_bindings(self, monkeypatch, requests_mock):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "deployer-function-bindings")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        requests_mock.register_uri("PUT", "https://storage.googleapis.com/mock")

        bindings = [{"role": "roles/cloudfunctions.invoker", "members": ["allUsers"]}]

        app = Goblet(
            function_name="goblet_bindings",
            config={"bindings": bindings},
        )
        setattr(app, "entrypoint", "app")

        app.handlers["http"] = HTTP("name", app)
        app.deploy(
            skip_handlers=True,
            skip_infra=True,
            force=True,
        )

        responses = get_responses("deployer-function-bindings")
        assert len(responses) == 4
        assert responses[2]["body"]["bindings"] == bindings

    def test_cloudfunction_delta(self, monkeypatch, requests_mock):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-east1")
        monkeypatch.setenv("G_TEST_NAME", "deployer-cloudfunction-delta")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        requests_mock.register_uri(
            "HEAD",
            "https://storage.googleapis.com/mock",
            headers={"x-goog-hash": "crc32c=+kjoHA==, md5=QcWxCkEOHzBSBgerQcjMEg=="},
        )

        app = Goblet(function_name="goblet_test_app")

        app_backend = app.backend_class(app)

        assert not app_backend.delta(f"{DATA_DIR_MAIN}/test_zip.txt.zip")
        assert app_backend.delta(f"{DATA_DIR_MAIN}/fail_test_zip.txt.zip")

    def test_cloudrun_custom_artifact(self, monkeypatch, requests_mock):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "deployer-cloudrun-artifact")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        requests_mock.register_uri("PUT", "https://storage.googleapis.com/mock")

        app = Goblet(
            function_name="goblet",
            backend="cloudrun",
            config={
                "deploy": {
                    "artifact_registry": "us-central1-docker.pkg.dev/newgoblet/cloud-run-source-deploy/goblet"
                },
                "cloudrun_revision": {
                    "serviceAccount": "test@goblet.iam.gserviceaccount.com"
                },
                "cloudbuild": {
                    "serviceAccount": "projects/goblet/serviceAccounts/test@goblet.iam.gserviceaccount.com",
                },
            },
        )
        setattr(app, "entrypoint", "app")

        app.handlers["http"] = HTTP("name", app)

        app.deploy(
            skip_handlers=True,
            skip_infra=True,
            force=True,
        )

        response = get_response(
            "deployer-cloudrun-artifact", "post-v1-projects-goblet-builds_1.json"
        )
        assert (
            "newgoblet"
            in response["body"]["metadata"]["build"]["artifacts"]["images"][0]
        )

    def test_cloudrun_artifact_tag(self, monkeypatch):
        G_TEST_NAME = "single-registry"
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", G_TEST_NAME)
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        artifact_tag = (
            "sha256:478c9c7b9b86d8ef6ae12998ef2ff6a0171c2163cf055c87969f0b886c6d67d7"
        )

        app = Goblet(
            function_name="goblet",
            backend="cloudrun",
            config={
                "deploy": {
                    "artifact_tag": artifact_tag,
                    "artifact_registry": "us-central1-docker.pkg.dev/goblet/cloud-run-source-deploy/single-registry",
                },
                "cloudrun_revision": {"serviceAccount": "service-accont@goblet.com"},
                "cloudbuild": {
                    "serviceAccount": "projects/goblet/serviceAccounts/service-accont@goblet.com"
                },
            },
        )
        setattr(app, "entrypoint", "app")

        app.handlers["http"] = HTTP("name", app, resources=[{}])

        app.deploy(skip_handlers=True, skip_infra=True, force=True)

        response = get_response(
            G_TEST_NAME, "post-v2-projects-goblet-locations-us-central1-services_1.json"
        )

        assert (
            artifact_tag
            in response["body"]["response"]["template"]["containers"][0]["image"]
        )

    def test_cloudrun_artifact_tag_from_env(self, monkeypatch):
        G_TEST_NAME = "single-registry"
        artifact_tag = (
            "sha256:478c9c7b9b86d8ef6ae12998ef2ff6a0171c2163cf055c87969f0b886c6d67d7"
        )
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", G_TEST_NAME)
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")
        monkeypatch.setenv("GOBLET_ARTIFACT_TAG", artifact_tag)

        app = Goblet(
            function_name="goblet",
            backend="cloudrun",
            config={
                "deploy": {
                    "artifact_registry": "us-central1-docker.pkg.dev/goblet/cloud-run-source-deploy/single-registry",
                },
                "cloudrun_revision": {"serviceAccount": "service-accont@goblet.com"},
                "cloudbuild": {
                    "serviceAccount": "projects/goblet/serviceAccounts/service-accont@goblet.com"
                },
            },
        )
        setattr(app, "entrypoint", "app")

        app.handlers["http"] = HTTP("name", app, resources=[{}])

        app.deploy(skip_handlers=True, skip_infra=True, force=True)

        response = get_response(
            G_TEST_NAME, "post-v2-projects-goblet-locations-us-central1-services_1.json"
        )

        assert (
            artifact_tag
            in response["body"]["response"]["template"]["containers"][0]["image"]
        )

    def test_cloudrun_no_default_registry(self, monkeypatch):
        G_TEST_NAME = "no-default-registry"
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-east1")
        monkeypatch.setenv("G_TEST_NAME", G_TEST_NAME)
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        app = Goblet(function_name="goblet", backend="cloudrun")
        setattr(app, "entrypoint", "app")

        app.handlers["http"] = HTTP("name", app, resources=[{}])

        app.deploy(skip_handlers=True, skip_infra=True, force=True)

        artifact_response = get_response(
            G_TEST_NAME,
            "get-v1-projects-goblet-locations-us-east1-repositories-cloud-run-source-deploy_1.json",
        )

        artifact_create_response = get_response(
            G_TEST_NAME,
            "post-v1-projects-goblet-locations-us-east1-repositories_1.json",
        )

        assert artifact_response["body"]["error"]["code"] == 404
        assert (
            "projects/goblet/locations/us-east1"
            in artifact_create_response["body"]["name"]
        )

    def test_cloudrun_build_tags(self, monkeypatch):
        G_TEST_NAME = "build-tags"
        tags = "test,dev"
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", G_TEST_NAME)
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")
        monkeypatch.setenv("GOBLET_BUILD_TAGS", tags)

        app = Goblet(
            function_name="goblet",
            backend="cloudrun",
            config={
                "cloudrun_revision": {"serviceAccount": "service-account@goblet.com"},
                "cloudbuild": {
                    "serviceAccount": "projects/goblet/serviceAccounts/service-accont@goblet.com"
                },
            },
        )
        setattr(app, "entrypoint", "app")

        app.handlers["http"] = HTTP("name", app, resources=[{}])

        app.deploy(skip_handlers=True, skip_infra=True, force=True)

        response = get_response(G_TEST_NAME, "post-v1-projects-goblet-builds_1.json")

        for image in response["body"]["metadata"]["build"]["images"]:
            assert any(tag in image for tag in tags.split(","))

    def test_cloudfunction_build_tags(self, monkeypatch, requests_mock):
        G_TEST_NAME = "cloudfunction-build-tags"
        tags = "test,dev"
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", G_TEST_NAME)
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")
        monkeypatch.setenv("GOBLET_BUILD_TAGS", tags)
        monkeypatch.setenv("GOBLET_UPLOAD_BUCKET", "bucket")

        requests_mock.register_uri("PUT", "https://storage.googleapis.com/mock")
        app = Goblet(function_name="cloudfunction-build-tags")
        goblet_entrypoint(app)
        setattr(app, "entrypoint", "app")

        app.handlers["http"] = HTTP("name", app, resources=[{}])
        app.deploy(skip_handlers=True, skip_infra=True, force=True)

        responses = get_responses(G_TEST_NAME)
        assert len(responses) == 4
