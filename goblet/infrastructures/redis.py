from goblet.infrastructures.infrastructure import Infrastructure
from googleapiclient.errors import HttpError
import logging

log = logging.getLogger("goblet.deployer")
log.setLevel(logging.INFO)


class Redis(Infrastructure):
    resource_type = "redis"
    update_keys = ["displayName", "labels", "memorySizeGb", "replicaCount"]

    def register(self, name, kwargs):
        self.resource = {"name": name}

    def deploy(self, config={}):
        if not self.resource:
            return
        self.config.update_g_config(values=config)
        redis_config = self.config.redis or {}
        req_body = {
            "tier": redis_config.get("tier", "BASIC"),
            "memorySizeGb": redis_config.get("memorySizeGb", 1),
            "labels": self.config.labels,
            **redis_config,
        }
        try:
            resp = self.client.redis.execute(
                "create",
                params={"instanceId": self.resource["name"], "body": req_body},
            )
            self.client.redis.wait_for_operation(resp["name"])
        except HttpError as e:
            if e.resp.status == 409:
                log.info(f"updating redis {self.resource['name']}")
                if req_body.get("tier") == "BASIC":
                    self.update_keys.remove("replicaCount")
                resp = self.client.redis.execute(
                    "patch",
                    parent_key="name",
                    parent_schema="projects/{project_id}/locations/{location_id}/instances/"
                    + self.resource["name"],
                    params={"updateMask": ",".join(self.update_keys), "body": req_body},
                )
                self.client.redis.wait_for_operation(resp["name"])
            else:
                raise e

    def destroy(self):
        try:
            if not self.resource:
                return
            resp = self.client.redis.execute(
                "delete",
                parent_key="name",
                parent_schema="projects/{project_id}/locations/{location_id}/instances/"
                + self.resource["name"],
            )
            self.client.redis.wait_for_operation(resp["name"])
            log.info(f"destroying redis {self.resource['name']}")
        except HttpError as e:
            if e.resp.status == 404:
                log.info(f"redis {self.resource['name']} already destroyed")
            else:
                raise e

    def get(self):
        if not self.resource:
            return
        resp = self.client.redis.execute(
            "get",
            parent_key="name",
            parent_schema="projects/{project_id}/locations/{location_id}/instances/"
            + self.resource["name"],
        )
        return resp

    def get_config(self):
        if not self.resource:
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
