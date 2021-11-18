from goblet.deploy import Deployer
from goblet.resources.http import HTTP
from goblet import Goblet
from goblet.test_utils import get_responses, dummy_function, DATA_DIR_MAIN


class TestDeployer:

    def test_deploy_http_function(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "deployer-function-deploy")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

        app = Goblet(function_name="goblet_example")
        setattr(app, "entrypoint", 'app')

        app.handlers['http'] = HTTP(dummy_function)

        Deployer().deploy(app, only_function=True, force=True)

        responses = get_responses('deployer-function-deploy')
        assert(len(responses) == 3)

    def test_destroy_http_function(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "deployer-function-destroy")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

        app = Goblet(function_name="goblet_example")

        Deployer().destroy(app)

        responses = get_responses('deployer-function-destroy')
        assert(len(responses) == 1)
        assert(responses[0]['body']['metadata']['type'] == 'DELETE_FUNCTION')
        assert(responses[0]['body']['metadata']['target'] == "projects/goblet/locations/us-central1/functions/goblet_test_app")

    def test_destroy_http_function_all(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "deployer-function-destroy-all")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

        app = Goblet(function_name="goblet_example")

        Deployer(config={'name': "goblet_example"}).destroy(app, all=True)

        responses = get_responses('deployer-function-destroy-all')
        assert(len(responses) == 4)

    def test_set_iam_bindings(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "deployer-function-bindings")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

        app = Goblet(function_name="goblet_bindings")
        setattr(app, "entrypoint", 'app')

        app.handlers['http'] = HTTP(dummy_function)
        bindings = [{"role": "roles/cloudfunctions.invoker", "members": ["allUsers"]}]
        Deployer().deploy(app, only_function=True, config={'bindings': bindings}, force=True)

        responses = get_responses('deployer-function-bindings')
        assert(len(responses) == 4)
        assert(responses[2]['body']['bindings'] == bindings)

    def test_cloudfunction_delta(self, monkeypatch, requests_mock):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-east1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "deployer-cloudfunction-delta")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

        requests_mock.register_uri("HEAD", 'https://storage.googleapis.com/mock', headers={'x-goog-hash': 'crc32c=+kjoHA==, md5=QcWxCkEOHzBSBgerQcjMEg=='})

        assert not Deployer()._cloudfunction_delta(f"{DATA_DIR_MAIN}/test_zip.txt.zip")
        assert Deployer()._cloudfunction_delta(f"{DATA_DIR_MAIN}/fail_test_zip.txt.zip")
