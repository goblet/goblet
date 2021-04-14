from goblet import Goblet
from goblet.resources.scheduler import Scheduler


class TestScheduler:

    def test_add_schedule(self, monkeypatch):
        app = Goblet(function_name="goblet_example", region='us-central-1')
        monkeypatch.setenv("GOOGLE_PROJECT", "TEST_PROJECT")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")

        @app.schedule('* * * * *', description='test')
        def dummy_function(self):
            return True
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

    def test_deploy_schedule(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PROJECT", "premise-governance-rd")
        monkeypatch.setenv("GOOGLE_LOCATION", "us-central1")
        monkeypatch.setenv("GOBLET_TEST_NAME", "schedule-deploy")
        monkeypatch.setenv("GOBLET_HTTP_TEST", "REPLAY")

        scheduler = Scheduler('test')
        scheduler.register_job('test-job', None, kwargs={'schedule':'* * * * *', 'kwargs': {}})
        scheduler.deploy()
        