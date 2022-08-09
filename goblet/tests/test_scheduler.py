from unittest.mock import Mock
from goblet import Goblet
from goblet.resources.scheduler import Scheduler
from goblet.test_utils import (
    get_responses,
    get_response,
    mock_dummy_function,
    dummy_function,
)


class TestScheduler:
    def test_add_schedule(self, monkeypatch):
        app = Goblet(function_name="goblet_example")
        monkeypatch.setenv("GOOGLE_PROJECT", "TEST_PROJECT")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")

        app.schedule("* * * * *", description="test")(dummy_function)

        scheduler = app.handlers["schedule"]
        assert len(scheduler.resources) == 1
        scheule_json = {
            "name": "projects/TEST_PROJECT/locations/us-central1/jobs/goblet_example-dummy_function",
            "schedule": "* * * * *",
            "timeZone": "UTC",
            "description": "test",
            "attemptDeadline": None,
            "retry_config": None,
            "httpTarget": {
                "body": None,
                "headers": {
                    "X-Goblet-Type": "schedule",
                    "X-Goblet-Name": "dummy_function",
                },
                "httpMethod": "GET",
                "oidcToken": {},
            },
        }
        assert scheduler.resources["dummy_function"]["job_json"] == scheule_json
        assert scheduler.resources["dummy_function"]["func"] == dummy_function

    def test_multiple_schedules(self, monkeypatch):
        app = Goblet(function_name="goblet_example")
        monkeypatch.setenv("GOOGLE_PROJECT", "TEST_PROJECT")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")

        app.schedule("1 * * * *", description="test")(dummy_function)
        app.schedule("2 * * * *", headers={"test": "header"})(dummy_function)
        app.schedule("3 * * * *", httpMethod="POST")(dummy_function)

        scheduler = app.handlers["schedule"]
        assert len(scheduler.resources) == 3
        scheule_json = {
            "name": "projects/TEST_PROJECT/locations/us-central1/jobs/goblet_example-dummy_function",
            "schedule": "1 * * * *",
            "timeZone": "UTC",
            "description": "test",
            "attemptDeadline": None,
            "retry_config": None,
            "httpTarget": {
                "body": None,
                "headers": {
                    "X-Goblet-Type": "schedule",
                    "X-Goblet-Name": "dummy_function",
                },
                "httpMethod": "GET",
                "oidcToken": {},
            },
        }
        assert scheduler.resources["dummy_function"]["job_json"] == scheule_json
        assert (
            scheduler.resources["dummy_function-2"]["job_json"]["httpTarget"][
                "headers"
            ]["test"]
            == "header"
        )
        assert (
            scheduler.resources["dummy_function-2"]["job_json"]["httpTarget"][
                "headers"
            ]["X-Goblet-Name"]
            == "dummy_function-2"
        )
        assert (
            scheduler.resources["dummy_function-3"]["job_json"]["httpTarget"][
                "headers"
            ]["X-Goblet-Name"]
            == "dummy_function-3"
        )
        assert (
            scheduler.resources["dummy_function-3"]["job_json"]["httpTarget"][
                "httpMethod"
            ]
            == "POST"
        )

    def test_call_scheduler(self, monkeypatch):
        app = Goblet(function_name="goblet_example")
        monkeypatch.setenv("GOOGLE_PROJECT", "TEST_PROJECT")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")

        mock = Mock()

        app.schedule("* * * * *", description="test")(mock_dummy_function(mock))

        headers = {
            "X-Goblet-Name": "dummy_function",
            "X-Goblet-Type": "schedule",
            "X-Cloudscheduler": True,
        }

        mock_event = Mock()
        mock_event.headers = headers

        app(mock_event, None)

        assert mock.call_count == 1

    def test_deploy_schedule(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "schedule-deploy")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

        goblet_name = "goblet_example"
        scheduler = Scheduler(goblet_name)
        scheduler.register_job(
            "test-job",
            None,
            kwargs={"schedule": "* * * * *", "timezone": "UTC", "kwargs": {}},
        )
        scheduler.deploy()

        responses = get_responses("schedule-deploy")

        assert goblet_name in responses[0]["body"]["name"]
        assert (
            responses[1]["body"]["httpTarget"]["headers"]["X-Goblet-Name"] == "test-job"
        )
        assert (
            responses[1]["body"]["httpTarget"]["headers"]["X-Goblet-Type"] == "schedule"
        )
        assert responses[1]["body"]["schedule"] == "* * * * *"

    def test_deploy_schedule_cloudrun(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "schedule-deploy-cloudrun")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

        scheduler = Scheduler("goblet", backend="cloudrun")
        cloudrun_url = "https://goblet-12345.a.run.app"
        service_account = "SERVICE_ACCOUNT@developer.gserviceaccount.com"
        scheduler.register_job(
            "test-job",
            None,
            kwargs={"schedule": "* * * * *", "timezone": "UTC", "kwargs": {}},
        )
        scheduler._deploy(config={"scheduler": {"serviceAccount": service_account}})

        responses = get_responses("schedule-deploy-cloudrun")

        assert responses[0]["body"]["status"]["url"] == cloudrun_url
        assert (
            responses[1]["body"]["httpTarget"]["oidcToken"]["serviceAccountEmail"]
            == service_account
        )
        assert (
            responses[1]["body"]["httpTarget"]["oidcToken"]["audience"] == cloudrun_url
        )
        assert responses[1]["body"]["schedule"] == "* * * * *"

    def test_deploy_multiple_schedule(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "schedule-deploy-multiple")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

        goblet_name = "goblet-test-schedule"
        scheduler = Scheduler(goblet_name)
        scheduler.register_job(
            "test-job",
            None,
            kwargs={"schedule": "* * 1 * *", "timezone": "UTC", "kwargs": {}},
        )
        scheduler.register_job(
            "test-job",
            None,
            kwargs={
                "schedule": "* * 2 * *",
                "timezone": "UTC",
                "kwargs": {"httpMethod": "POST"},
            },
        )
        scheduler.register_job(
            "test-job",
            None,
            kwargs={
                "schedule": "* * 3 * *",
                "timezone": "UTC",
                "kwargs": {"headers": {"X-HEADER": "header"}},
            },
        )
        scheduler.deploy()

        post_job_1 = get_response(
            "schedule-deploy-multiple",
            "post-v1-projects-goblet-locations-us-central1-jobs_1.json",
        )
        post_job_2 = get_response(
            "schedule-deploy-multiple",
            "post-v1-projects-goblet-locations-us-central1-jobs_2.json",
        )
        post_job_3 = get_response(
            "schedule-deploy-multiple",
            "post-v1-projects-goblet-locations-us-central1-jobs_3.json",
        )

        assert (
            post_job_1["body"]["httpTarget"]["headers"]["X-Goblet-Name"] == "test-job"
        )
        assert (
            post_job_2["body"]["httpTarget"]["headers"]["X-Goblet-Name"] == "test-job-2"
        )
        assert post_job_2["body"]["httpTarget"]["httpMethod"] == "POST"
        assert (
            post_job_3["body"]["httpTarget"]["headers"]["X-Goblet-Name"] == "test-job-3"
        )
        assert post_job_3["body"]["httpTarget"]["headers"]["X-HEADER"] == "header"

    def test_destroy_schedule(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "schedule-destroy")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

        goblet_name = "goblet_example"
        scheduler = Scheduler(goblet_name)
        scheduler.register_job(
            "test-job",
            None,
            kwargs={"schedule": "* * * * *", "timezone": "UTC", "kwargs": {}},
        )
        scheduler.destroy()

        responses = get_responses("schedule-destroy")

        assert len(responses) == 1
        assert responses[0]["body"] == {}

    def test_sync_schedule(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "schedule-sync")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

        goblet_name = "goblet"
        scheduler = Scheduler(goblet_name)
        scheduler.register_job(
            "scheduled_job",
            None,
            kwargs={"schedule": "* * * * *", "timezone": "UTC", "kwargs": {}},
        )
        scheduler.sync(dryrun=True)
        scheduler.sync(dryrun=False)

        responses = get_responses("schedule-sync")
        assert len(responses) == 3
        assert responses[1] == responses[2]
        assert responses[0]["body"] == {}
