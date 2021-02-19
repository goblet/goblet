import logging

from goblet.handler import Handler
from goblet.client import Client, get_default_project, get_default_location
from googleapiclient.errors import HttpError

log = logging.getLogger('goblet.deployer')
log.setLevel(logging.INFO)


class Scheduler(Handler):
    def __init__(self, name, routes={}):
        self.cloudfunction = f"projects/{get_default_project()}/locations/{get_default_location()}/functions/{name}"
        self.jobs = {}
        self._api_client = None

    @property
    def api_client(self):
        if not self._api_client:
            self._api_client = self._create_api_client()
        return self._api_client

    def _create_api_client(self):
        return Client("cloudscheduler", 'v1', calls='projects.locations.jobs', parent_schema='projects/{project_id}/locations/{location_id}')

    def register_job(self, name, func, kwargs):
        schedule = kwargs["schedule"]
        kwargs = kwargs.pop('kwargs')
        timezone = kwargs.get("timezone", 'UTC')
        description = kwargs.get("description", "Created by goblet")
        self.jobs[name] = {
            "job_json": {
                "name": f"projects/{get_default_project()}/locations/{get_default_location()}/jobs/{name}",
                "schedule": schedule,
                "timeZone": timezone,
                "description": description,
                "httpTarget": {
                    # "uri": ADDED AT runtime,
                    "headers": {
                        'X-Goblet-Type': 'schedule',
                        'X-Goblet-Name': name
                    },
                    "httpMethod": "GET",
                    'oidcToken': {
                        # "serviceAccountEmail": ADDED AT runtime
                    }
                }
            },
            "func": func
        }

    def __call__(self, request, context=None):
        headers = request.headers
        func_name = headers.get("X-Goblet-Name")
        if not func_name:
            raise ValueError("No X-Goblet-Name header found")

        job = self.jobs[func_name]
        if not job:
            raise ValueError(f"Function {func_name} not found")
        return job["func"]()

    def __add__(self, other):
        self.jobs.update(other.jobs)
        return self

    def deploy(self):
        if not self.jobs:
            return

        cloudfunction_client = Client("cloudfunctions", 'v1', calls='projects.locations.functions', parent_schema='projects/{project_id}/locations/{location_id}')
        resp = cloudfunction_client.execute('get', parent_key="name", parent_schema=self.cloudfunction)
        if not resp:
            raise ValueError(f"Function {self.cloudfunction} not found")
        cloudfunction_target = resp["httpsTrigger"]["url"]
        service_account = resp["serviceAccountEmail"]

        log.info("deploying scheduled jobs......")
        for job_name, job in self.jobs.items():
            job["job_json"]["httpTarget"]['uri'] = cloudfunction_target
            job["job_json"]["httpTarget"]['oidcToken']["serviceAccountEmail"] = service_account

            self.deploy_job(job_name, job["job_json"])

    def deploy_job(self, job_name, job):
        try:
            self.api_client.execute('create', params={'body': job})
            log.info(f"created scheduled job: {job_name}")
        except HttpError as e:
            if e.resp.status == 409:
                log.info(f"updated scheduled job: {job_name}")
                self.api_client.execute('patch', parent_key="name", parent_schema=job['name'], params={'body': job})
            else:
                raise e

    def destroy(self):
        for job_name in self.jobs.keys():
            self._destroy_job(job_name)

    def _destroy_job(self, job_name):
        try:
            scheduler_client = Client("cloudscheduler", 'v1', calls='projects.locations.jobs', parent_schema='projects/{project_id}/locations/{location_id}/jobs/' + job_name)
            scheduler_client.execute('delete', parent_key="name")
            log.info("destroying scheduled functions......")
        except HttpError as e:
            if e.resp.status == 404:
                log.info("scheduled functions already destroyed")
            else:
                raise e
