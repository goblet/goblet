from goblet_gcp_client import get_response

from goblet import Goblet


class TestServices:
    def test_check_service_apis_status(self, monkeypatch):
        app = Goblet(function_name="test-goblet-services")
        monkeypatch.setenv("G_TEST_NAME", "services-check")
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")
        app.services(enable=False)

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
        app.services(enable=True)

        resp = get_response(
            "services-enable",
            "post-v1-projects-goblet-services-batchEnable_1.json",
        )

        resources = resp["body"]["metadata"]["resourceNames"]
        assert "cloudfunctions" in resources[0]
        assert "secretmanager" in resources[1]
