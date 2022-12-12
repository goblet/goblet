from goblet import Goblet
from goblet.backends.backend import Backend
from goblet.backends import CloudFunctionV1, CloudFunctionV2, CloudRun


class TestBackend:
    def test_custom_files(self, monkeypatch):
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

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
