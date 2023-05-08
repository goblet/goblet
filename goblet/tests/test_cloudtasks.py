import pytest

from goblet import Goblet, Response
from goblet_gcp_client import get_response

from goblet.infrastructures.cloudtask import CloudTaskClient
from unittest.mock import Mock


class TestCloudTasks:
    def test_add_cloudtaskqueues(self):
        app = Goblet(
            function_name="goblet_example",
            config={"cloudtask": {"serviceAccount": "service-account@goblet.com"}},
        )

        app.cloudtaskqueue(name="cloudtaskqueue01")
        app.cloudtaskqueue(name="cloudtaskqueue02")

        cloudtaskqueue = app.infrastructure["cloudtaskqueue"]
        assert cloudtaskqueue.resource["cloudtaskqueue01"]["id"] == "cloudtaskqueue01"
        assert cloudtaskqueue.resource["cloudtaskqueue02"]["id"] == "cloudtaskqueue02"

    def test_deploy_cloudtaskqueue(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "cloudtaskqueue-deploy")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        app = Goblet(
            function_name="goblet_example",
            config={"cloudtask": {"serviceAccount": "service-account@goblet.com"}},
        )

        client: CloudTaskClient = app.cloudtaskqueue(  # noqa: F841
            name="cloudtaskqueue"
        )

        app.deploy(
            force=True,
            skip_backend=True,
            skip_resources=True,
        )

        post_cloudtaskqueue = get_response(
            "cloudtaskqueue-deploy",
            "post-v2-projects-goblet-locations-us-central1-queues_1.json",
        )

        assert post_cloudtaskqueue["body"]["state"] == "RUNNING"

    def test_destroy_cloudtaskqueue(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "cloudtaskqueue-deploy")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        app = Goblet(
            function_name="goblet_example",
            config={"cloudtask": {"serviceAccount": "service-account@goblet.com"}},
        )

        client: CloudTaskClient = app.cloudtaskqueue(  # noqa: F841
            name="cloudtaskqueue"
        )

        app.destroy()

        delete_cloudtaskqueue = get_response(
            "cloudtaskqueue-deploy",
            "delete-v2-projects-goblet-locations-us-central1-queues-cloudtaskqueue_1.json",
        )

        assert delete_cloudtaskqueue["body"] == {}

    def test_enqueue_task(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("G_TEST_NAME", "cloudtaskqueue-deploy")
        monkeypatch.setenv("G_HTTP_TEST", "REPLAY")

        app = Goblet(
            function_name="goblet_example",
            config={"cloudtask": {"serviceAccount": "service-account@goblet.com"}},
        )

        client: CloudTaskClient = app.cloudtaskqueue(name="cloudtaskqueue")

        app.deploy(
            force=True,
            skip_backend=True,
            skip_resources=True,
        )

        @app.cloudtasktarget(name="target")
        def my_handler(request):
            pass

        payload = {
            "userContext": {"targetFunction": "my_handler"},
            "task_body": {"key": "value"},
        }
        client.enqueue(target="target", payload=payload)

        enqueue_task = get_response(
            "cloudtaskqueue-deploy",
            "post-v2-projects-goblet-locations-us-central1-queues-cloudtaskqueue-tasks_1.json",
        )
        assert enqueue_task["body"]["name"].startswith(
            "projects/goblet/locations/us-central1/queues/cloudtaskqueue/tasks"
        )
        assert (
            enqueue_task["body"]["httpRequest"]["headers"]["X-Goblet-CloudTask-Target"]
            == "target"
        )

    def test_build_task(self):
        backend = Mock()
        backend.http_endpoint = "http_endpoint"
        client = CloudTaskClient("service_account", "queue", backend)
        task = client.build_task(
            "target", {"message": {"title": "enqueue"}}, 60, "task_name", 120
        )

        assert task["name"] == "queue/tasks/task_name"
        assert task["dispatchDeadline"] == "120s"
        assert task["scheduleTime"] is not None
        assert task["httpRequest"]["headers"]["X-Goblet-CloudTask-Target"] == "target"
        assert task["httpRequest"]["url"] == backend.http_endpoint
        assert (
            task["httpRequest"]["oidcToken"]["serviceAccountEmail"] == "service_account"
        )
        assert task["httpRequest"]["oidcToken"]["audience"] == backend.http_endpoint
        assert (
            task["httpRequest"]["body"]
            == "eyJtZXNzYWdlIjogeyJ0aXRsZSI6ICJlbnF1ZXVlIn19"
        )

    def test_duplicate_targets(self):
        app = Goblet(function_name="goblet_example")

        with pytest.raises(Exception):

            @app.cloudtasktarget(name="target")
            def dummy_function(task):
                return {}

            @app.cloudtasktarget(name="target")
            def dummy_function2(task):
                return {}

    def test_handle_cloud_task(self):
        app = Goblet(function_name="goblet_example")

        @app.cloudtasktarget(name="target")
        def dummy_function(task):
            return Response("200", status_code=200)

        headers = {
            "User-Agent": "Google-Cloud-Tasks",
            "X-Goblet-CloudTask-Target": "target",
        }

        mock_request = Mock()
        mock_request.json = {}
        mock_request.headers = headers

        assert app(mock_request, None).status_code == 200
