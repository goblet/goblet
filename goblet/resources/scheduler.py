import logging

from goblet.handler import Handler
from goblet.client import Client, get_default_project, get_default_location
from goblet.common_cloud_actions import get_cloudrun_url
from goblet.config import GConfig

from googleapiclient.errors import HttpError

log = logging.getLogger("goblet.deployer")
log.setLevel(logging.INFO)


class Scheduler(Handler):
    """Cloud Scheduler job which calls http endpoint
    https://cloud.google.com/scheduler/docs
    """

    resource_type = "scheduler"
    valid_backends = ["cloudfunction", "cloudrun"]

    def __init__(self, name, resources=None, backend="cloudfunction"):
        self.name = name
        self.backend = backend
        self.cloudfunction = f"projects/{get_default_project()}/locations/{get_default_location()}/functions/{name}"
        self.resources = resources or {}
        self._api_client = None

    @property
    def api_client(self):
        if not self._api_client:
            self._api_client = self._create_api_client()
        return self._api_client

    def _create_api_client(self):
        return Client(
            "cloudscheduler",
            "v1",
            calls="projects.locations.jobs",
            parent_schema="projects/{project_id}/locations/{location_id}",
        )

    def register_job(self, name, func, kwargs):
        schedule = kwargs["schedule"]
        kwargs = kwargs.pop("kwargs")
        timezone = kwargs.get("timezone", "UTC")
        description = kwargs.get("description", "Created by goblet")
        headers = kwargs.get("headers", {})
        httpMethod = kwargs.get("httpMethod", "GET")
        retry_config = kwargs.get("retryConfig")
        body = kwargs.get("body")
        attempt_deadline = kwargs.get("attemptDeadline")

        job_num = 1
        if self.resources.get(name):
            # increment job_num if there is already a scheduled job for this func
            job_num = self.resources[name]["job_num"] + 1
            self.resources[name]["job_num"] = job_num
            name = f"{name}-{job_num}"
        self.resources[name] = {
            "job_num": job_num,
            "job_json": {
                "name": f"projects/{get_default_project()}/locations/{get_default_location()}/jobs/{self.name}-{name}",
                "schedule": schedule,
                "timeZone": timezone,
                "description": description,
                "retry_config": retry_config,
                "attemptDeadline": attempt_deadline,
                "httpTarget": {
                    # "uri": ADDED AT runtime,
                    "headers": {
                        "X-Goblet-Type": "schedule",
                        "X-Goblet-Name": name,
                        **headers,
                    },
                    "body": body,
                    "httpMethod": httpMethod,
                    "oidcToken": {
                        # "serviceAccountEmail": ADDED AT runtime
                    },
                },
            },
            "func": func,
        }

    def __call__(self, request, context=None):
        headers = request.headers
        func_name = headers.get("X-Goblet-Name")
        if not func_name:
            raise ValueError("No X-Goblet-Name header found")

        job = self.resources[func_name]
        if not job:
            raise ValueError(f"Function {func_name} not found")
        return job["func"]()

    def _deploy(self, sourceUrl=None, entrypoint=None, config={}):
        if not self.resources:
            return

        if self.backend == "cloudfunction":
            cloudfunction_client = Client(
                "cloudfunctions",
                "v1",
                calls="projects.locations.functions",
                parent_schema="projects/{project_id}/locations/{location_id}",
            )
            resp = cloudfunction_client.execute(
                "get", parent_key="name", parent_schema=self.cloudfunction
            )
            if not resp:
                raise ValueError(f"Function {self.cloudfunction} not found")
            target = resp["httpsTrigger"]["url"]
            service_account = resp["serviceAccountEmail"]

        if self.backend == "cloudrun":
            target = get_cloudrun_url(self.name)
            config = GConfig(config=config)
            if config.cloudrun and config.cloudrun.get("service-account"):
                service_account = config.cloudrun.get("service-account")
            elif config.scheduler and config.scheduler.get("serviceAccount"):
                service_account = config.scheduler.get("serviceAccount")
            else:
                raise ValueError(
                    "Service account not found in cloudrun. You can set `serviceAccount` field in config.json under `scheduler`"
                )
        log.info("deploying scheduled jobs......")
        for job_name, job in self.resources.items():
            job["job_json"]["httpTarget"]["uri"] = target
            job["job_json"]["httpTarget"]["oidcToken"][
                "serviceAccountEmail"
            ] = service_account

            self.deploy_job(job_name, job["job_json"])

    def deploy_job(self, job_name, job):
        try:
            self.api_client.execute("create", params={"body": job})
            log.info(f"created scheduled job: {job_name} for {self.name}")
        except HttpError as e:
            if e.resp.status == 409:
                log.info(f"updated scheduled job: {job_name} for {self.name}")
                self.api_client.execute(
                    "patch",
                    parent_key="name",
                    parent_schema=job["name"],
                    params={"body": job},
                )
            else:
                raise e

    def destroy(self):
        if not self.resources:
            return
        for job_name in self.resources.keys():
            self._destroy_job(job_name)

    def _destroy_job(self, job_name):
        try:
            scheduler_client = Client(
                "cloudscheduler",
                "v1",
                calls="projects.locations.jobs",
                parent_schema="projects/{project_id}/locations/{location_id}/jobs/"
                + self.name
                + "-"
                + job_name,
            )
            scheduler_client.execute("delete", parent_key="name")
            log.info("destroying scheduled functions......")
        except HttpError as e:
            if e.resp.status == 404:
                log.info("scheduled functions already destroyed")
            else:
                raise e
