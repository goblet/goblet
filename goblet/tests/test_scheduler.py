from unittest.mock import Mock
from goblet import Goblet
from goblet.resources.scheduler import Scheduler
from goblet.test_utils import get_responses, mock_dummy_function, dummy_function


class TestScheduler:

    def test_add_schedule(self, monkeypatch):
        app = Goblet(function_name="goblet_example")
        monkeypatch.setenv("GOOGLE_PROJECT", "TEST_PROJECT")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")

        app.schedule('* * * * *', description='test')(dummy_function)

        scheduler = app.handlers["schedule"]
        assert(len(scheduler.jobs) == 1)
        scheule_json = {
            'name': 'projects/TEST_PROJECT/locations/us-central1/jobs/goblet_example-dummy_function',
            'schedule': '* * * * *',
            'timeZone': 'UTC',
            'description': 'test',
            'httpTarget': {
                'headers': {
                    'X-Goblet-Type': 'schedule',
                    'X-Goblet-Name': 'dummy_function',
                },
                'httpMethod': 'GET',
                'oidcToken': {}
            }
        }
        assert(scheduler.jobs['dummy_function']['job_json'] == scheule_json)
        assert(scheduler.jobs['dummy_function']['func'] == dummy_function)

    def test_call_scheduler(self, monkeypatch):
        app = Goblet(function_name="goblet_example")
        monkeypatch.setenv("GOOGLE_PROJECT", "TEST_PROJECT")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")

        mock = Mock()

        app.schedule('* * * * *', description='test')(mock_dummy_function(mock))

        headers = {
            "X-Goblet-Name": "dummy_function",
            "X-Goblet-Type": "schedule",
            "X-Cloudscheduler": True
        }

        mock_event = Mock()
        mock_event.headers = headers

        app(mock_event, None)

        assert(mock.call_count == 1)

    def test_deploy_schedule(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "schedule-deploy")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

        goblet_name = 'goblet_example'
        scheduler = Scheduler(goblet_name)
        scheduler.register_job('test-job', None, kwargs={'schedule': '* * * * *', 'kwargs': {}})
        scheduler.deploy()

        responses = get_responses('schedule-deploy')

        assert(goblet_name in responses[0]['body']['name'])
        assert(responses[1]['body']['httpTarget']['headers']['X-Goblet-Name'] == 'test-job')
        assert(responses[1]['body']['httpTarget']['headers']['X-Goblet-Type'] == 'schedule')
        assert(responses[1]['body']['schedule'] == '* * * * *')

    def test_destroy_schedule(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "schedule-destroy")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

        goblet_name = 'goblet_example'
        scheduler = Scheduler(goblet_name)
        scheduler.register_job('test-job', None, kwargs={'schedule': '* * * * *', 'kwargs': {}})
        scheduler.destroy()

        responses = get_responses('schedule-destroy')

        assert(len(responses) == 1)
        assert(responses[0]['body'] == {})
