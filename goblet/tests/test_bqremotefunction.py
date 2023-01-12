from pprint import pprint
from unittest.mock import Mock
from goblet import Goblet
from goblet.resources.scheduler import Scheduler
from goblet.test_utils import (
    get_responses,
    get_response,
    mock_dummy_function,
    dummy_function,
)
from goblet.backends import CloudRun, CloudFunctionV1


# from goblet.resources.bq_remote_function import get_hints


class TestBqRemoteFunction:
    # def test_register_bqremotefunction(self, monkeypatch):
    #     app = Goblet(function_name="goblet_example")
    #     monkeypatch.setenv("GOOGLE_PROJECT", "TEST_PROJECT")
    #     monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
    #
    #     test_name = "test-bqremoterefunction"
    #     test_dataset_id = "test-dataset"
    #
    #     app.bqremotefunction(func=dummy_function, name=test_name, dataset_id=test_dataset_id)
    #
    #     bqremotefunction_handler = app.handlers[test_name]
    #
    #     input, output = get_hints(dummy_function)
    #
    #     expected_resources = {
    #         "routine_name": test_name,
    #         "dataset_id": test_dataset_id,
    #         "inputs": input,
    #         "output": output,
    #         "func": dummy_function
    #     }
    #     assert expected_resources["routine_name"] == bqremotefunction_handler["routine_name"]
    #     assert expected_resources["dataset_id"] == bqremotefunction_handler["dataset_id"]
    #     assert expected_resources["inputs"] == bqremotefunction_handler["inputs"]
    #     assert expected_resources["output"] == bqremotefunction_handler["output"]
    #     assert expected_resources["func"] == bqremotefunction_handler["func"]
    #
    # def test_call_bqremotefunction(self, monkeypatch):
    #     app = Goblet(function_name="goblet_example")
    #     monkeypatch.setenv("GOOGLE_PROJECT", "TEST_PROJECT")
    #     monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
    #
    #     mock = Mock()
    #
    #     app.bqremotefunction()(mock_dummy_function(mock))
    #
    #     headers = {
    #         "X-Goblet-Name": "dummy_function"
    #     }
    #
    #     mock_event = Mock()
    #     mock_event.headers = headers
    #
    #     app(mock_event, None)
    #
    #     assert mock.call_count == 1

    def test_deploy_bqremotefunction(self, monkeypatch):
        test_deploy_name = "bqremotefunction-deploy"
        # FOR RECORDING
        # monkeypatch.setenv("GOOGLE_PROJECT", "premise-data-platform-dev")
        # FOR REPLAY
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", test_deploy_name)
        # FOR RECORDING
        # monkeypatch.setenv("GOBLET_HTTP_TEST", "RECORD")
        # FOR REPLAY
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

        test_name = "bqremotefunction_test"
        app = Goblet(function_name=test_name)
        test_dataset_id = "blogs"
        app.handlers["http"].register_http(dummy_function, {})

        app.bqremotefunction(
            func=dummy_function, name=test_name, dataset_id=test_dataset_id
        )

        app.deploy(force=True)
        responses = get_responses(test_deploy_name)
        assert len(responses) > 0

        # Check Connection
        connections = list(request["body"] for request in responses if "cloudResource" in request["body"])
        assert len(connections) == 1
        assert "serviceAccountId" in connections[0]["cloudResource"]
        assert "bigquery" in connections[0]["cloudResource"]["serviceAccountId"]
        assert test_name in connections[0]["name"]

        # Check policy
        bindings = list(request["body"]["bindings"] for request in responses if "bindings" in request["body"])
        assert len(bindings) == 1
        assert "members" in bindings[0][0]
        members = bindings[0][0]["members"]
        assert len(members) == 1 and "serviceAccount" in members[0]
        assert "role" in bindings[0][0]
        assert bindings[0][0]["role"] == "roles/cloudfunctions.invoker"

    # def test_destroy_bqremotefunction(self, monkeypatch):
    #     test_deploy_name = "bqremotefunction-destroy"
    #     # FOR RECORDING
    #     # monkeypatch.setenv("GOOGLE_PROJECT", "premise-data-platform-dev")
    #     # FOR REPLAY
    #     monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
    #     monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
    #     monkeypatch.setenv("GOBLET_TEST_NAME", test_deploy_name)
    #     # FOR RECORDING
    #     # monkeypatch.setenv("GOBLET_HTTP_TEST", "RECORD")
    #     # FOR REPLAY
    #     monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")
    #
    #     test_name = "bqremotefunction_test"
    #     app = Goblet(function_name=test_name)
    #     test_dataset_id = "blogs"
    #     app.bqremotefunction(
    #         func=dummy_function, name=test_name, dataset_id=test_dataset_id
    #     )
    #     app.handlers["http"].register_http(dummy_function, {})
    #     app.destroy()
    #     responses = get_responses(test_deploy_name)
    #
    #     assert len(responses) != 0
    #
    #     bodies = list(response["body"] for response in responses)
    #
    #     deleted_function = list(body["metadata"] for body in bodies if "metadata" in body and "type" in body["metadata"] and "type" in body["metadata"] and "DELETE_FUNCTION" == body["metadata"]["type"])
    #     assert len(deleted_function) == 1
    #     assert f"functions/{test_name}" in deleted_function[0]["target"]
    def test_sync_bqremotefunction(self, monkeypatch):
        test_deploy_name = "bqremotefunction-sync"
        # FOR RECORDING
        monkeypatch.setenv("GOOGLE_PROJECT", "premise-data-platform-dev")
        # FOR REPLAY
        # monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", test_deploy_name)
        # FOR RECORDING
        monkeypatch.setenv("GOBLET_HTTP_TEST", "RECORD")
        # FOR REPLAY
        # monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

        test_name = "bqremotefunction_test"
        app = Goblet(function_name=test_name)
        test_dataset_id = "blogs"
        app.bqremotefunction(
            func=dummy_function, name=test_name, dataset_id=test_dataset_id
        )
        app.handlers["http"].register_http(dummy_function, {})

        app.sync(dryrun=True)
        app.sync(dryrun=False)

        responses = get_responses("bqremotefunction-sync")
        pprint(responses)