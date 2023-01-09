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
                "apiVersion": "run.googleapis.com/v1",
                "kind": "Job",
                "metadata": {
                    "name": job_name,
                    "annotations": {"run.googleapis.com/launch-stage": "BETA"},
                    "labels": gconfig.labels,
                },
                "spec": {
                    "template": {
                        "metadata": {"annotations": annotations},
                        "spec": {
                            "taskCount": len(job.keys()) - 1,
                            "template": {
                                "spec": {
                                    "containers": [container],
                                    **(gconfig.job_spec or {}),
                                }
                            },
                        },
                        **job["execution_spec"],
                    }
                },
            }

            self.deploy_job(job_name, job_spec)

    def _sync(self, dryrun=False):
        jobs = self.versioned_clients.run_job.execute("list").get("items", [])
        filtered_jobs = list(
            filter(lambda job: self.name in job["metadata"]["name"], jobs)
        )
        for filtered_job in filtered_jobs:
            filtered_name = filtered_job["metadata"]["name"]
            if not self.resources.get(filtered_name):
                log.info(f"Detected unused job in GCP {filtered_name}")
                if not dryrun:
                    self._destroy_job(filtered_name)

    def deploy_job(self, job_name, job):
        try:
            self.versioned_clients.run_job.execute("create", params={"body": job})
            log.info(f"created job: {job_name}")
        except HttpError as e:
            if e.resp.status == 409:
                log.info(f"updated job: {job_name}")
                self.versioned_clients.run_job.execute(
                    "replaceJob",
                    parent_key="name",
                    parent_schema="namespaces/{project_id}/jobs/" + job_name,
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
            self.versioned_clients.run_job.execute(
                "delete",
                parent_key="name",
                parent_schema="namespaces/{project_id}/jobs/" + job_name,
            )
            log.info(f"Destroying job {job_name}......")
        except HttpError as e:
            if e.resp.status == 404:
                log.info("Jobs already destroyed")
            else:
                raise e
