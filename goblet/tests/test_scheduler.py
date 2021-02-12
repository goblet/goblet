from goblet import Goblet
import os


class TestScheduler:

    def test_add_schedule(self):
        app = Goblet(function_name="goblet_example", region='us-central-1')
        os.environ["GOOGLE_PROJECT"] = "TEST_PROJECT"
        os.environ["GOOGLE_LOCATION"] = "us-central1"

        @app.schedule('* * * * *', description='test')
        def dummy_function(self):
            return True

        scheduler = app.handlers["schedule"]
        assert(len(scheduler.jobs) == 1)
        scheule_json = {
            'name': 'projects/TEST_PROJECT/locations/us-central1/jobs/dummy_function',
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
