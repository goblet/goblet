from goblet.deploy import Deployer
from goblet.resources.http import HTTP
from goblet import Goblet
from goblet.test_utils import get_responses, dummy_function


class TestDeployer:

    def test_deploy_http_function(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "deployer-function-deploy")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

        app = Goblet(function_name="goblet_example", region='us-central-1')
        setattr(app, "entrypoint", 'app')

        app.handlers['http'] = HTTP(dummy_function)

        Deployer().deploy(app, only_function=True)

        responses = get_responses('deployer-function-deploy')
        assert(len(responses) == 3)

    def test_destroy_http_function(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "deployer-function-destroy")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

        app = Goblet(function_name="goblet_example", region='us-central-1')

        Deployer().destroy(app)

        responses = get_responses('deployer-function-destroy')
        assert(len(responses) == 1)
        assert(responses[0]['body']['metadata']['type'] == 'DELETE_FUNCTION')
        assert(responses[0]['body']['metadata']['target'] == "projects/goblet/locations/us-central1/functions/goblet_test_app")

    def test_set_iam_bindings(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "deployer-function-bindings")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

        app = Goblet(function_name="goblet_bindings")
        setattr(app, "entrypoint", 'app')

        app.handlers['http'] = HTTP(dummy_function)
        bindings = [{"role": "roles/cloudfunctions.invoker", "members": ["allUsers"]}]
        Deployer().deploy(app, only_function=True, config={'bindings': bindings})

        responses = get_responses('deployer-function-bindings')
        assert(len(responses) == 4)
        assert(responses[2]['body']['bindings'] == bindings)
