from unittest.mock import Mock
from goblet import Goblet
from goblet.resources.scheduler import Scheduler
from goblet.test_utils import get_responses, get_response, mock_dummy_function, dummy_function


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
                'body': None,
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

    def test_multiple_schedules(self, monkeypatch):
        app = Goblet(function_name="goblet_example")
        monkeypatch.setenv("GOOGLE_PROJECT", "TEST_PROJECT")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")

        app.schedule('1 * * * *', description='test')(dummy_function)
        app.schedule('2 * * * *', headers={'test': 'header'})(dummy_function)
        app.schedule('3 * * * *', httpMethod='POST')(dummy_function)

        scheduler = app.handlers["schedule"]
        assert(len(scheduler.jobs) == 3)
        scheule_json = {
            'name': 'projects/TEST_PROJECT/locations/us-central1/jobs/goblet_example-dummy_function',
            'schedule': '1 * * * *',
            'timeZone': 'UTC',
            'description': 'test',
            'httpTarget': {
                'body': None,
                'headers': {
                    'X-Goblet-Type': 'schedule',
                    'X-Goblet-Name': 'dummy_function',
                },
                'httpMethod': 'GET',
                'oidcToken': {}
            }
        }
        assert(scheduler.jobs['dummy_function']['job_json'] == scheule_json)
        assert(scheduler.jobs['dummy_function-2']['job_json']['httpTarget']['headers']['test'] == 'header')
        assert(scheduler.jobs['dummy_function-2']['job_json']['httpTarget']['headers']['X-Goblet-Name'] == 'dummy_function-2')
        assert(scheduler.jobs['dummy_function-3']['job_json']['httpTarget']['headers']['X-Goblet-Name'] == 'dummy_function-3')
        assert(scheduler.jobs['dummy_function-3']['job_json']['httpTarget']['httpMethod'] == 'POST')

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

    def test_deploy_multiple_schedule(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "goblet")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "schedule-deploy-multiple")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

        goblet_name = 'goblet-test-schedule'
        scheduler = Scheduler(goblet_name)
        scheduler.register_job('test-job', None, kwargs={'schedule': '* * 1 * *', 'kwargs': {}})
        scheduler.register_job('test-job', None, kwargs={'schedule': '* * 2 * *', 'kwargs': {'httpMethod': 'POST'}})
        scheduler.register_job('test-job', None, kwargs={'schedule': '* * 3 * *', 'kwargs': {'headers': {'X-HEADER': 'header'}}})
        scheduler.deploy()

        post_job_1 = get_response('schedule-deploy-multiple', 'post-v1-projects-goblet-locations-us-central1-jobs_1.json')
        post_job_2 = get_response('schedule-deploy-multiple', 'post-v1-projects-goblet-locations-us-central1-jobs_2.json')
        post_job_3 = get_response('schedule-deploy-multiple', 'post-v1-projects-goblet-locations-us-central1-jobs_3.json')

        assert(post_job_1['body']['httpTarget']['headers']['X-Goblet-Name'] == 'test-job')
        assert(post_job_2['body']['httpTarget']['headers']['X-Goblet-Name'] == 'test-job-2')
        assert(post_job_2['body']['httpTarget']['httpMethod'] == 'POST')
        assert(post_job_3['body']['httpTarget']['headers']['X-Goblet-Name'] == 'test-job-3')
        assert(post_job_3['body']['httpTarget']['headers']['X-HEADER'] == 'header')

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
