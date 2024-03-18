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
        assert len(responses) == 7
        assert "test-job-test" in responses[5]["body"]["metadata"]["name"]

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

    def test_job_iam_bindings(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "job-iam-bindings")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        app = Goblet(
            function_name="goblet-test",
            backend="cloudrun",
            config={
                "scheduler": {"serviceAccount": "test@goblet.iam.gserviceaccount.com"},
                "bindings": [
                    {
                        "role": "roles/run.invoker",
                        "members": ["user:test.user@goblet.com"],
                    }
                ],
            },
        )
        app.job("test", schedule="10 10 * * *")(dummy_function)
        app.deploy(force=True, skip_backend=True)

        job_bindings = get_response(
            "job-iam-bindings",
            "post-v2-projects-goblet-locations-us-central1-jobs-goblet-test-test-setIamPolicy_1.json",
        )
        assert (
            job_bindings["body"]["bindings"][0]["members"][0]
            == "user:test.user@goblet.com"
        )
        assert len(job_bindings["body"]["bindings"][0]["members"]) == 1

        schedule_bindings = get_response(
            "job-iam-bindings",
            "post-v2-projects-goblet-locations-us-central1-jobs-goblet-test-test-setIamPolicy_2.json",
        )
        assert (
            schedule_bindings["body"]["bindings"][0]["members"][1]
            == "user:test.user@goblet.com"
        )
        assert (
            schedule_bindings["body"]["bindings"][0]["members"][0]
            == "serviceAccount:test@goblet.iam.gserviceaccount.com"
        )
        assert len(schedule_bindings["body"]["bindings"][0]["members"]) == 2

    def test_deploy_jobs_from_artifact_tag(self, monkeypatch):
        artifact_tag = (
            "sha256:0a05e8ee3a7a3527dee34999247e29f19c4cf7941750a3267bb9b1a2f37b724a"
        )
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "jobs/deploy-from-artifact-tag")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")
        monkeypatch.setenv("GOBLET_ARTIFACT_TAG", artifact_tag)

        app = Goblet(function_name="goblet-jobs", backend="cloudrun")
        app.job("test-artifact-tag")(dummy_function)
        app.deploy()

        responses = get_responses("jobs/deploy-from-artifact-tag")
        assert len(responses) == 3
        assert (
            artifact_tag
            in responses[1]["body"]["metadata"]["template"]["template"]["containers"][
                0
            ]["image"]
        )

    def test_schedule_with_stages(self, monkeypatch):
        monkeypatch.setenv("STAGE", "TEST")

        app = Goblet("test", backend="cloudrun", config={"stages": {"TEST": {}}})

        @app.job("testjob1", schedule="* * * * *")
        @app.stage("TEST")
        def dummy_function():
            return "test"

        @app.job("testjob2", schedule="* * * * *")
        @app.stage("TEST2")
        def dummy_function2():
            return "test"

        @app.job("testjob3", schedule="* * * * *")
        @app.stage(stages=["TEST", "TEST2"])
        def dummy_function3():
            return "test"

        assert list(app.handlers["schedule"].resources.keys()) == [
            "schedule-job-testjob1",
            "schedule-job-testjob3",
        ]

    def test_schedule_without_stages(self, monkeypatch):
        monkeypatch.setenv("STAGE", "TEST")

        app = Goblet("test", backend="cloudrun", config={"stages": {"TEST": {}}})

        @app.job("testjob1", schedule="* * * * *")
        def dummy_function():
            return "test"

        assert list(app.handlers["schedule"].resources.keys()) == [
            "schedule-job-testjob1"
        ]
