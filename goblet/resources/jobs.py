import logging

from goblet.resources.handler import Handler
from goblet.common_cloud_actions import getCloudbuildArtifact
from goblet.config import GConfig

from googleapiclient.errors import HttpError

log = logging.getLogger("goblet.deployer")
log.setLevel(logging.INFO)


class Jobs(Handler):
    """Cloudrun job
    https://cloud.google.com/run/docs/create-jobs
    """

    resource_type = "job"
    valid_backends = ["cloudrun"]
    can_sync = True

    def register(self, name, func, kwargs):
        task_id = kwargs["task_id"]
        job_name = f"{self.name}-{kwargs['name']}"
        if self.resources.get(job_name):
            self.resources[job_name][task_id] = {"func": func}
        else:
            self.resources[job_name] = {
                task_id: {"func": func},
                "execution_spec": kwargs.get("kwargs", {}),
            }

    def __call__(self, name, task_id):
        if not self.resources.get(name):
            raise ValueError(f"Job {name} not found")

        if not self.resources[name].get(task_id):
            raise ValueError(
                f"Job {name} not found for CLOUD_RUN_TASK_INDEX: {task_id}"
            )

        job = self.resources[name][task_id]

        return job["func"](task_id)

    def _deploy(self, source=None, entrypoint=None, config={}):
        if not self.resources:
            return

        gconfig = GConfig(config=config)
        artifact = getCloudbuildArtifact(
            self.versioned_clients.cloudbuild, self.name, config=gconfig
        )

        log.info("deploying cloudrun jobs......")
        for job_name, job in self.resources.items():
            container = {**(gconfig.job_container or {})}
            annotations = {**(gconfig.job_annotations or {})}
            container["image"] = artifact
            container["command"] = [
                "goblet",
                "job",
                "run",
                job_name,
            ]

            job_spec = {
                "launchStage": "BETA",
                "labels": gconfig.labels,
                "template": {
                    "annotations": annotations,
                    "taskCount": len(job.keys()) - 1,
                    "template": {
                        "containers": [container],
                        **(gconfig.job_spec or {}),
                    },
                    **job["execution_spec"],
                },
            }

            self.deploy_job(job_name, job_spec)
            service_account_ids = []
            if job_sa := (gconfig.job_spec or {}).get("serviceAccount"):
                service_account_ids.append(job_sa)
            if scheduler_sa := (gconfig.scheduler or {}).get("serviceAccount"):
                service_account_ids.append(scheduler_sa)
            if service_account_ids:
                self.set_iam_policy(job_name, service_account_ids)

    def _sync(self, dryrun=False):
        jobs = self.versioned_clients.run_job.execute("list").get("jobs", [])
        filtered_jobs = list(filter(lambda job: self.name in job["name"], jobs))
        for filtered_job in filtered_jobs:
            filtered_name = filtered_job["name"].split("jobs/")[-1]
            if not self.resources.get(filtered_name):
                log.info(f"Detected unused job in GCP {filtered_name}")
                if not dryrun:
                    self._destroy_job(filtered_name)

    def deploy_job(self, job_name, job):
        try:
            resp = self.versioned_clients.run_job.execute(
                "create", params={"jobId": job_name, "body": job}
            )
            self.versioned_clients.run_job.wait_for_operation(resp["name"])
            log.info(f"created job: {job_name}")
        except HttpError as e:
            if e.resp.status == 409:
                resp = self.versioned_clients.run_job.execute(
                    "patch",
                    parent_key="name",
                    parent_schema="projects/{project_id}/locations/{location_id}/jobs/"
                    + job_name,
                    params={"body": job},
                )
                self.versioned_clients.run_job.wait_for_operation(resp["name"])
                log.info(f"updated job: {job_name}")
            else:
                raise e

    def destroy(self):
        if not self.resources:
            return
        for job_name in self.resources.keys():
            self._destroy_job(job_name)

    def _destroy_job(self, job_name):
        try:
            resp = self.versioned_clients.run_job.execute(
                "delete",
                parent_key="name",
                parent_schema="projects/{project_id}/locations/{location_id}/jobs/"
                + job_name,
            )
            self.versioned_clients.run_job.wait_for_operation(resp["name"])
            log.info(f"Destroying job {job_name}......")
        except HttpError as e:
            if e.resp.status == 404:
                log.info("Jobs already destroyed")
            else:
                raise e

    def set_iam_policy(self, job_name, service_account_ids):
        policy = {
            "policy": {
                "bindings": {
                    "role": "roles/run.invoker",
                    "members": [
                        f"serviceAccount:{sa_id}" for sa_id in service_account_ids
                    ],
                }
            }
        }
        self.versioned_clients.run_job.execute(
            "setIamPolicy",
            params={"body": policy},
            parent_key="resource",
            parent_schema="projects/{project_id}/locations/{location_id}/jobs/"
            + job_name,
        )
        log.info(f"set iam policy for job {job_name}")
