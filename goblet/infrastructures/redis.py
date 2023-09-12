from goblet.infrastructures.infrastructure import Infrastructure
from goblet.permissions import gcp_generic_resource_permissions
from googleapiclient.errors import HttpError
import logging
import os

log = logging.getLogger("goblet.deployer")
log.setLevel(logging.getLevelName(os.getenv("GOBLET_LOG_LEVEL", "INFO")))


class Redis(Infrastructure):
    resource_type = "redis"
    update_keys = ["displayName", "labels", "memorySizeGb", "replicaCount"]
    required_apis = ["redis"]
    permissions = [
        "redis.operations.get",
        gcp_generic_resource_permissions("redis", "instances"),
    ]

    def register(self, name, kwargs):
        self.resources = {"name": name}

    def _deploy(self):
        if not self.resources:
            return
        redis_config = self.config.redis or {}
        req_body = {
            "tier": redis_config.get("tier", "BASIC"),
            "memorySizeGb": redis_config.get("memorySizeGb", 1),
            "labels": self.config.labels,
            **redis_config,
        }
        try:
            resp = self.versioned_clients.redis.execute(
                "create",
                params={"instanceId": self.resources["name"], "body": req_body},
            )
            self.versioned_clients.redis.wait_for_operation(resp["name"])
        except HttpError as e:
            if e.resp.status == 409:
                log.info(f"updating redis {self.resources['name']}")
                if req_body.get("tier") == "BASIC":
                    self.update_keys.remove("replicaCount")
                resp = self.versioned_clients.redis.execute(
                    "patch",
                    parent_key="name",
                    parent_schema="projects/{project_id}/locations/{location_id}/instances/"
                    + self.resources["name"],
                    params={"updateMask": ",".join(self.update_keys), "body": req_body},
                )
                self.versioned_clients.redis.wait_for_operation(resp["name"])
            else:
                raise e

    def destroy(self):
        try:
            if not self.resources:
                return
            resp = self.versioned_clients.redis.execute(
                "delete",
                parent_key="name",
                parent_schema="projects/{project_id}/locations/{location_id}/instances/"
                + self.resources["name"],
            )
            self.versioned_clients.redis.wait_for_operation(resp["name"])
            log.info(f"destroying redis {self.resources['name']}")
        except HttpError as e:
            if e.resp.status == 404:
                log.info(f"redis {self.resources['name']} already destroyed")
            else:
                raise e

    def get(self):
        if not self.resources:
            return
        resp = self.versioned_clients.redis.execute(
            "get",
            parent_key="name",
            parent_schema="projects/{project_id}/locations/{location_id}/instances/"
            + self.resources["name"],
        )
        return resp

    def get_config(self):
        if not self.resources:
            return
        redis = self.get()
        return {
            "resource_type": self.resource_type,
            "values": {
                "REDIS_INSTANCE_NAME": redis["name"],
                "REDIS_HOST": redis["host"],
                "REDIS_PORT": f"{redis['port']}",
            },
        }
