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
        monkeypatch.setenv("GOOGLE_PROJECT", "premise-data-platform-dev")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "bqremotefunction-deploy")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "RECORD")

        app = Goblet(function_name="bqremotefunction_test3")
        test_name = "bqremotefunction_test3"
        test_dataset_id = "blogs"
        # app.handlers["http"].register_http(dummy_function, {})

        app.bqremotefunction(
            func=dummy_function, name=test_name, dataset_id=test_dataset_id
        )

        app.deploy(force=True)
        #
        # goblet_name = "goblet_example"
        # scheduler = Scheduler(goblet_name, backend=CloudFunctionV1(Goblet()))
        # scheduler.register_job(
        #     "test-job",
        #     None,
        #     kwargs={"schedule": "* * * * *", "timezone": "UTC", "kwargs": {}},
        # )
        # scheduler.deploy()

        # responses = get_responses("schedule-deploy")
        #
        # assert goblet_name in responses[0]["body"]["name"]
        # assert (
        #         responses[1]["body"]["httpTarget"]["headers"]["X-Goblet-Name"] == "test-job"
        # )
        # assert (
        #         responses[1]["body"]["httpTarget"]["headers"]["X-Goblet-Type"] == "schedule"
        # )
        # assert responses[1]["body"]["schedule"] == "* * * * *"

    # def test_destroy_bqremotefunction(self, monkeypatch):
    #     monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
    #     monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
    #     monkeypatch.setenv("GOBLET_TEST_NAME", "schedule-destroy")
    #     monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")
    #
    #     goblet_name = "goblet_example"
    #     scheduler = Scheduler(
    #         goblet_name, backend=CloudFunctionV1(Goblet(function_name=goblet_name))
    #     )
    #     scheduler.register_job(
    #         "test-job",
    #         None,
    #         kwargs={"schedule": "* * * * *", "timezone": "UTC", "kwargs": {}},
    #     )
    #     scheduler.destroy()
    #
    #     responses = get_responses("schedule-destroy")
    #
    #     assert len(responses) == 1
    #     assert responses[0]["body"] == {}
    #
    # def test_sync_bqremotefunction(self, monkeypatch):
    #     monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
    #     monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
    #     monkeypatch.setenv("GOBLET_TEST_NAME", "schedule-sync")
    #     monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")
    #
    #     goblet_name = "goblet"
    #     scheduler = Scheduler(goblet_name, backend=CloudFunctionV1(Goblet()))
    #     scheduler.register_job(
    #         "scheduled_job",
    #         None,
    #         kwargs={"schedule": "* * * * *", "timezone": "UTC", "kwargs": {}},
    #     )
    #     scheduler.sync(dryrun=True)
    #     scheduler.sync(dryrun=False)
    #
    #     responses = get_responses("schedule-sync")
    #     assert len(responses) == 3
    #     assert responses[1] == responses[2]
    #     assert responses[0]["body"] == {}
