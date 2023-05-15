from unittest.mock import Mock
from goblet import Goblet
from goblet.handlers.jobs import Jobs
import pytest

from goblet.test_utils import (
    dummy_function,
    mock_dummy_function,
)

from goblet_gcp_client import get_responses, get_response


from goblet.backends import CloudRun


class TestJobs:
    def test_add_job(self):
        app = Goblet(function_name="goblet_example")

        app.job("test")(dummy_function)

        jobs = app.handlers["jobs"]
        assert len(jobs.resources) == 1
        assert jobs.resources[f"{app.function_name}-test"].get(0)

    def test_add_job_tasks(self):
        app = Goblet(function_name="goblet_example")

        app.job("test")(dummy_function)
        app.job("test", task_id=1)(dummy_function)
        app.job("test", task_id=2)(dummy_function)

        jobs = app.handlers["jobs"]
        assert len(jobs.resources) == 1
        assert jobs.resources[f"{app.function_name}-test"].get(0)
        assert jobs.resources[f"{app.function_name}-test"].get(1)
        assert jobs.resources[f"{app.function_name}-test"].get(2)

    def test_add_job_tasks_valid_kwargs(self):
        app = Goblet(function_name="goblet_example")

        with pytest.raises(Exception):
            app.job("test", task_id=1, schedule="* * * * *")(dummy_function)

        with pytest.raises(Exception):
            app.job("test", task_id=1, extra_arg="test")(dummy_function)

    def test_add_job_with_schedule(self):
        app = Goblet(function_name="goblet_example")

        app.job("test", schedule="* * * * *")(dummy_function)

        jobs = app.handlers["jobs"]
        assert len(jobs.resources) == 1
        assert jobs.resources[f"{app.function_name}-test"].get(0)
        scheduler = app.handlers["schedule"]
        assert len(scheduler.resources) == 1
        assert scheduler.resources["schedule-job-test"]["authMethod"] == "oauthToken"
        assert scheduler.resources["schedule-job-test"]["uri"]

    def test_call_job(self, monkeypatch):
        app = Goblet(function_name="goblet_example")
        monkeypatch.setenv("CLOUD_RUN_TASK_INDEX", "0")

        mock = Mock()
        mock2 = Mock()

        app = Goblet(function_name="goblet_example")
        app.job("test")(mock_dummy_function(mock))
        app.job("test", task_id=1)(mock_dummy_function(mock2))

        app("goblet_example-test", 0)
        app("goblet_example-test", 1)

        assert mock.call_count == 1
        assert mock2.call_count == 1

    def test_deploy_job(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "job-deploy")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        app = Goblet(function_name="test-job", backend="cloudrun")
        app.job("test")(dummy_function)
        app.deploy(force=True)

        responses = get_responses("job-deploy")
        assert len(responses) == 6
        assert "test-job-test" in responses[4]["body"]["metadata"]["name"]

    def test_deploy_job_schedule(self, monkeypatch, requests_mock):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "job-deploy-schedule")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        requests_mock.register_uri("PUT", "https://storage.googleapis.com/mock")

        app = Goblet(
            function_name="goblet-test",
            backend="cloudrun",
            config={"scheduler": {"serviceAccount": "test@goblet.com"}},
        )
        app.job("test", schedule="* * * * *")(dummy_function)
        app.deploy(force=True)

        scheduler = get_response(
            "job-deploy-schedule",
            "post-v1-projects-goblet-locations-us-central1-jobs_1.json",
        )
        assert (
            scheduler["body"]["httpTarget"]["uri"]
            == "https://us-central1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/goblet/jobs/goblet-test-test:run"
        )
        job = get_response(
            "job-deploy-schedule",
            "post-v2-projects-goblet-locations-us-central1-jobs_1.json",
        )
        assert "goblet-test-test" in job["body"]["metadata"]["name"]

        iam = get_response(
            "job-deploy-schedule",
            "post-v2-projects-goblet-locations-us-central1-jobs-goblet-test-test-setIamPolicy_1.json",
        )
        assert "test@goblet." in iam["body"]["bindings"][0]["members"][0]

    def test_sync_job(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "job-sync")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        goblet_name = "test-job"
        jobs = Jobs(goblet_name, CloudRun(Goblet(function_name="test-job")))
        jobs.register("test2", None, {"task_id": 0, "name": "test"})
        jobs.sync()

        responses = get_responses("job-sync")
        assert len(responses) == 3
        assert "test-job-test2" not in responses[0]["body"]["metadata"]["name"]

    def test_destroy_job(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "job-destroy")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        goblet_name = "goblet-test"
        jobs = Jobs(goblet_name, CloudRun(Goblet(function_name=goblet_name)))
        jobs.register("test", None, {"task_id": 0, "name": "test"})
        jobs.destroy()

        responses = get_responses("job-destroy")
        assert len(responses) == 2
        assert "goblet-test-test" in responses[0]["body"]["metadata"]["name"]
