from goblet_gcp_client import get_response

from goblet import Goblet

from goblet.common_cloud_actions import get_artifact_image_name


class TestCommonActions:
    def test_get_artifact_image_name(self, monkeypatch):
        monkeypatch.setenv("GOBLET_ARTIFACT_TAG", "test-tag-1")
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        image_name = get_artifact_image_name(None, "test-artifact", Goblet().config)
        assert (
            image_name
            == "us-central1-docker.pkg.dev/goblet/cloud-run-source-deploy/test-artifact:test-tag-1"
        )

    def test_get_artifact_image_name_with_registry(self, monkeypatch):
        monkeypatch.setenv("GOBLET_ARTIFACT_TAG", "test-tag-1")
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")

        app = Goblet(
            config={
                "deploy": {
                    "artifact_registry": "us-central1-docker.pkg.dev/goblet/repo-name/test-artifact"
                }
            },
        )

        image_name = get_artifact_image_name(None, "test-artifact", app.config)
        assert (
            image_name
            == "us-central1-docker.pkg.dev/goblet/repo-name/test-artifact:test-tag-1"
        )

    def test_check_service_apis_status(self, monkeypatch):
        app = Goblet(function_name="test-goblet-services")
        monkeypatch.setenv("G_TEST_NAME", "services-check")
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")
        app.check_or_enable_services()

        resp = get_response(
            "services-check",
            "get-v1-projects-goblet-services-batchGet_1.json",
        )

        services = resp["body"]["services"]
        assert "cloudfunctions" in services[0]["name"]
        assert "secretmanager" in services[1]["name"]

    def test_enable_service_apis(self, monkeypatch):
        app = Goblet(function_name="test-goblet-services")
        monkeypatch.setenv("G_TEST_NAME", "services-enable")
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")
        app.check_or_enable_services(enable=True)

        resp = get_response(
            "services-enable",
            "post-v1-projects-goblet-services-batchEnable_1.json",
        )

        resources = resp["body"]["metadata"]["resourceNames"]
        assert "cloudfunctions" in resources[0]
        assert "secretmanager" in resources[1]
