import pytest

from goblet import Goblet
from goblet.backends.backend import Backend
from goblet.backends import CloudFunctionV1, CloudFunctionV2, CloudRun
from goblet.errors import GobletValidationError


class TestBackend:
    def test_custom_files(self, monkeypatch):
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        test_custom_files = {
            "custom_files": {"include": ["*.yaml"], "exclude": [".secret"]}
        }
        backend = Backend(Goblet(), None, None, config=test_custom_files)

        assert "*.yaml" in backend.zip_config["include"]
        assert "*.py" in backend.zip_config["include"]
        assert ".secret" in backend.zip_config["exclude"]
        assert "build" in backend.zip_config["exclude"]

    def test_get_env_cloudfunction_v1(self):
        test_env = {"cloudfunction": {"environmentVariables": {"TEST": "VALUE"}}}
        backend = CloudFunctionV1(Goblet(), config=test_env)

        assert backend.get_environment_vars() == {"TEST": "VALUE"}

    def test_get_env_cloudfunction_v2(self):
        test_env = {
            "cloudfunction": {
                "serviceConfig": {"environmentVariables": {"TEST": "VALUE"}}
            }
        }
        backend = CloudFunctionV2(Goblet(), config=test_env)

        assert backend.get_environment_vars() == {"TEST": "VALUE"}

    def test_get_env_cloudrun(self):
        test_env = {"cloudrun_container": {"env": [{"name": "TEST", "value": "VALUE"}]}}
        backend = CloudRun(Goblet(), config=test_env)

        assert backend.get_environment_vars() == {"TEST": "VALUE"}

    def test_get_env_cloudrun_secret(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "get-secrets")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        test_env = {
            "cloudrun_container": {
                "env": [
                    {
                        "name": "TESTSECRET",
                        "valueSource": {
                            "secretKeyRef": {"secret": "TESTSECRET", "version": "1"}
                        },
                    }
                ]
            }
        }
        backend = CloudRun(Goblet(), config=test_env)

        assert backend.get_environment_vars() == {"TESTSECRET": "testtesttest"}

    def test_get_env_cloudfunction_secret(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "get-secrets")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        test_env = {
            "cloudfunction": {
                "secretEnvironmentVariables": [
                    {"key": "TESTSECRET", "secret": "TESTSECRET", "version": "1"},
                ]
            }
        }
        backend = CloudFunctionV1(Goblet(), config=test_env)

        assert backend.get_environment_vars() == {"TESTSECRET": "testtesttest"}

    def test_cloudrun_valid_name(self):
        with pytest.raises(GobletValidationError):
            CloudRun(Goblet(function_name="INVALID"))

        with pytest.raises(GobletValidationError):
            CloudRun(Goblet(function_name="in_valid"))

        CloudRun(Goblet(function_name="valid"))

    def test_cloudfunctionv2_valid_name(self):
        with pytest.raises(GobletValidationError):
            CloudFunctionV2(Goblet(function_name="INVALID"))

        with pytest.raises(GobletValidationError):
            CloudFunctionV2(Goblet(function_name="in_valid"))

        CloudFunctionV2(Goblet(function_name="valid"))
