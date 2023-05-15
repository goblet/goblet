import json
from unittest.mock import Mock
from goblet import Goblet
from goblet_gcp_client import get_responses
from goblet.handlers.bq_remote_function import BigQueryRemoteFunction
from typing import List


class TestBqRemoteFunction:
    def test_register_bqremotefunction(self, monkeypatch):
        app = Goblet(function_name="bqremotefunction_test")
        monkeypatch.setenv("GOOGLE_PROJECT", "TEST_PROJECT")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")

        test_dataset_id = "blogs"

        @app.bqremotefunction(dataset_id="blogs")
        def string_test_blogs_1(x: str, y: str) -> str:
            return f"Passed parameters x:{x}  y:{y}"

        resources = app.handlers["bqremotefunction"].resources

        input, output = BigQueryRemoteFunction(
            "bqremotefunction_test", "cloudrun"
        )._get_hints(string_test_blogs_1)

        expected_resources = {
            "routine_name": "bqremotefunction_test_string_test_blogs_1",
            "dataset_id": test_dataset_id,
            "vectorized_func": False,
            "max_batching_rows": 0,
            "inputs": input,
            "output": output,
            "func": string_test_blogs_1,
        }

        for resource_name, resource in resources.items():
            assert expected_resources["routine_name"] == resource["routine_name"]
            assert expected_resources["dataset_id"] == resource["dataset_id"]
            assert json.dumps(expected_resources["inputs"]) == json.dumps(
                resource["inputs"]
            )
            assert json.dumps(expected_resources["output"]) == json.dumps(
                resource["output"]
            )
            assert expected_resources["func"] == resource["func"]

    def test_call_bqremotefunction_vectorize(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "TEST_PROJECT")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")

        test_name = "bqremotefunction_test"
        app = Goblet(function_name=test_name)

        @app.bqremotefunction(dataset_id="blogs", vectorize_func=True)
        def function_test(x: List[int], y: List[str]) -> List[str]:
            return [f"{x[0]}{y[0]}", f"{x[1]}{y[1]}"]

        body = {
            "userDefinedContext": {
                "X-Goblet-Name": "bqremotefunction_test_function_test"
            },
            "calls": [[2, "a"], [3, "b"]],
        }

        mock_request = Mock()
        mock_request.json = body
        mock_request.headers = {}

        result = json.loads(app(mock_request, None))

        assert result["replies"][0] == "2a"
        assert result["replies"][1] == "3b"

    def test_call_bqremotefunction(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "TEST_PROJECT")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")

        test_name = "bqremotefunction_test"
        app = Goblet(function_name=test_name)

        @app.bqremotefunction(dataset_id="blogs")
        def function_test(x: int, y: int) -> int:
            return x * y

        body = {
            "userDefinedContext": {
                "X-Goblet-Name": "bqremotefunction_test_function_test"
            },
            "calls": [[2, 2], [3, 3]],
        }

        mock_request = Mock()
        mock_request.json = body
        mock_request.headers = {}

        result = json.loads(app(mock_request, None))

        assert result["replies"][0] == 4
        assert result["replies"][1] == 9

    def test_deploy_bqremotefunction(self, monkeypatch):
        test_deploy_name = "bqremotefunction-deploy"
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", test_deploy_name)
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        test_name = "bqremotefunction_test"
        app = Goblet(function_name=test_name)

        @app.bqremotefunction(dataset_id="blogs")
        def string_test_blogs_1(x: str, y: str) -> str:
            return f"Passed parameters x:{x}  y:{y}"

        app.deploy(force=True)
        responses = get_responses(test_deploy_name)
        assert len(responses) > 0
        # Check Connection
        connections = list(
            request["body"]
            for request in responses
            if "cloudResource" in request["body"]
        )
        assert len(connections) == 1
        assert "serviceAccountId" in connections[0]["cloudResource"]
        assert "bigquery" in connections[0]["cloudResource"]["serviceAccountId"]
        assert test_name in connections[0]["name"]

        # Check policy
        bindings = list(
            request["body"]["bindings"]
            for request in responses
            if "bindings" in request["body"]
        )
        assert len(bindings) == 1
        assert "members" in bindings[0][0]
        members = bindings[0][0]["members"]
        assert len(members) == 1 and "serviceAccount" in members[0]
        assert "role" in bindings[0][0]
        assert bindings[0][0]["role"] == "roles/cloudfunctions.invoker"

        routines = list(
            request["body"]
            for request in responses
            if "remoteFunctionOptions" in request["body"]
        )
        assert len(routines) == 1
        routine = routines[0]
        remote_function_options = routine["remoteFunctionOptions"]
        user_defined_context = (
            '{"X-Goblet-Name": "bqremotefunction_test_string_test_blogs_1"}'
        )
        assert (
            "connection" in remote_function_options
            and test_name in remote_function_options["connection"]
        )
        assert user_defined_context == json.dumps(
            remote_function_options["userDefinedContext"]
        )

    def test_destroy_bqremotefunction(self, monkeypatch):
        test_deploy_name = "bqremotefunction-destroy"
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", test_deploy_name)
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        test_name = "bqremotefunction_test"
        app = Goblet(function_name=test_name)

        @app.bqremotefunction(dataset_id="blogs")
        def string_test_blogs_1(x: str, y: str) -> str:
            return f"Passed parameters x:{x}  y:{y}"

        app.destroy()
        responses = get_responses(test_deploy_name)

        assert len(responses) != 0

        bodies = list(response["body"] for response in responses)

        deleted_function = list(
            body["metadata"]
            for body in bodies
            if "metadata" in body
            and "type" in body["metadata"]
            and "type" in body["metadata"]
            and "DELETE_FUNCTION" == body["metadata"]["type"]
        )
        assert len(deleted_function) == 1
        assert f"functions/{test_name}" in deleted_function[0]["target"]

    # def test_sync_bqremotefunction(self, monkeypatch):
    #     test_deploy_name = "bqremotefunction-sync"
    #     # FOR REPLAY
    #     # monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
    #     monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
    #     monkeypatch.setenv("G_TEST_NAME", test_deploy_name)
    #     # FOR REPLAY
    #     # monke-ypatch.setenv("G_HTTP_TEST", "REPLAY")
    #
    #     test_name = "bqremotefunction_test"
    #     app = Goblet(function_name=test_name)
    #
    #     app.handlers["bqremotefunction"].sync(dryrun=False)
    #     responses = get_responses("bqremotefunction-sync")
    #     #todo assert here!
