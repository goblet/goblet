import json
from base64 import b64encode
from googleapiclient.errors import HttpError
from goblet.infrastructures.infrastructure import Infrastructure
from goblet.permissions import gcp_generic_resource_permissions
import logging
import os
import datetime
from google.protobuf import duration_pb2, timestamp_pb2
from goblet.client import VersionedClients

log = logging.getLogger("goblet.deployer")
log.setLevel(logging.getLevelName(os.getenv("GOBLET_LOG_LEVEL", "INFO")))


class CloudTaskClient:
    def __init__(self, service_account, queue, backend):
        self.service_account = service_account
        self.queue = queue
        self.backend = backend

    def build_task(self, target, payload, in_seconds, task_name, deadline):
        # https://cloud.google.com/tasks/docs/reference/rest/v2/projects.locations.queues.tasks/create
        task = {
            "httpRequest": {
                "httpMethod": "POST",
                "headers": {
                    "X-Goblet-CloudTask-Target": target,
                },
                "url": self.backend.http_endpoint,
                "oidcToken": {
                    "serviceAccountEmail": self.service_account,
                    "audience": self.backend.http_endpoint,
                },
            }
        }

        if payload is not None:
            if isinstance(payload, dict):
                # Convert dict to JSON string
                payload = json.dumps(payload)
                # specify http content-type to application/json
                task["httpRequest"]["headers"]["Content-Type"] = "application/json"

            # The API expects a payload of type bytes.
            converted_payload = b64encode(payload.encode()).decode("utf8")
            # Add the payload to the request.
            task["httpRequest"]["body"] = converted_payload

        if in_seconds is not None:
            # Convert "seconds from now" into an rfc3339 datetime string.
            d = datetime.datetime.utcnow() + datetime.timedelta(seconds=in_seconds)

            # Create Timestamp protobuf.
            timestamp = timestamp_pb2.Timestamp()
            timestamp.FromDatetime(d)

            # Add the timestamp to the tasks.
            task["scheduleTime"] = timestamp.ToJsonString()

        if task_name is not None:
            # Add the name to tasks.
            task["name"] = f"{self.queue}/tasks/{task_name}"

        if deadline is not None:
            # Add dispatch deadline for requests sent to the worker.
            duration = duration_pb2.Duration()
            duration.FromSeconds(deadline)
            task["dispatchDeadline"] = duration.ToJsonString()

        return task

    def enqueue(self, target, payload, in_seconds=None, task_name=None, deadline=None):
        task = self.build_task(target, payload, in_seconds, task_name, deadline)
        return VersionedClients().cloudtask.execute(
            "create", parent_schema=self.queue, params={"body": {"task": task}}
        )


class CloudTaskQueue(Infrastructure):
    resource_type = "cloudtaskqueue"
    required_apis = ["cloudtasks"]
    permissions = gcp_generic_resource_permissions("cloudtasks", "queues")

    # https://cloud.google.com/apis/design/resource_names
    def register(self, name, kwargs):
        queue_config = kwargs.get("config", None)
        resource_id = name
        if (
            not queue_config
            and self.config.cloudtaskqueue
            and self.config.cloudtaskqueue.get(resource_id, None)
        ):
            queue_config = self.config.cloudtaskqueue.get(resource_id)
        self.resources[resource_id] = {
            "name": f"{self.versioned_clients.cloudtask_queue.parent}/queues/{resource_id}",
            "id": resource_id,
            "config": queue_config,
        }

        return CloudTaskClient(
            service_account=self.config.cloudtask.get("serviceAccount", None),
            queue=self.resources[resource_id]["name"],
            backend=self.backend,
        )

    def _deploy(self):
        if not self.resources:
            return

        for resource_id, resource in self.resources.items():
            params = {"name": resource["name"]}
            if resource["config"]:
                params = {**params, **resource["config"]}

            try:
                self.versioned_clients.cloudtask_queue.execute(
                    "create", params={"body": params}
                )
                log.info(f'CloudTask Queue [{resource["id"]}] deployed')

            except HttpError as e:
                if e.resp.status == 409:
                    log.info(f'found cloudtask queue {resource["id"]}')

                    if self.should_patch(resource["id"]):
                        self.versioned_clients.cloudtask_queue.execute(
                            "patch",
                            parent_key="name",
                            parent_schema=resource["name"],
                            params={"body": params},
                        )
                        log.info(f"CloudTask Queue [{resource['id']}] patched")
                else:
                    raise e

    def destroy(self):
        if not self.resources:
            return
        for resource_id, resource in self.resources.items():
            try:
                resp = self.versioned_clients.cloudtask_queue.execute(
                    "delete", parent_key="name", parent_schema=resource["name"]
                )
                if resp == {}:
                    log.info(f"CloudTask Queue [{resource['id']}] destroyed")
            except HttpError as e:
                if e.resp.status == 404:
                    log.info(f"cloudtask queue {resource['id']} already destroyed")
                else:
                    raise e

    def should_patch(self, resource_id):
        # if there is user config, there is nothing to compare with
        if not self.resources[resource_id].get("config"):
            return False

        deployed_config = self.get_deployed_config(resource_id)
        for section, configurations in self.resources[resource_id]["config"].items():
            for k, v in configurations.items():
                try:
                    # a value set in the desired config is
                    # different from the value deployed
                    if deployed_config[section][k] != v:
                        return True
                except KeyError:
                    log.info(f"config {section}.{k} not found in deployed config")
                except Exception as e:
                    raise e

        return False

    def get_deployed_config(self, resource_id):
        deployed_config = self.get(resource_id)
        return {
            "rateLimits": deployed_config["rateLimits"],
            "retryConfig": deployed_config["retryConfig"],
        }

    def get(self, resource_id):
        if not self.resources or not resource_id:
            return
        return self.versioned_clients.cloudtask_queue.execute(
            "get", parent_key="name", parent_schema=self.resources[resource_id]["name"]
        )

    def get_config(self, config={}):
        if not self.resources:
            return

        return {"resource_type": self.resource_type, "values": {}}
