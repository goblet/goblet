import logging
import os

from goblet.handlers.handler import Handler
from goblet.permissions import gcp_generic_resource_permissions
from goblet.utils import nested_update
from goblet_gcp_client.client import get_default_project, get_default_location
from googleapiclient.errors import HttpError

log = logging.getLogger("goblet.deployer")
log.setLevel(logging.getLevelName(os.getenv("GOBLET_LOG_LEVEL", "INFO")))


class Uptime(Handler):
    """Uptime Trigger
    Uptime checks only support public https urls and cloud run revisions currently https://cloud.google.com/monitoring/uptime-checks
    """

    resource_type = "uptime"
    valid_backends = ["cloudfunction", "cloudfunctionv2", "cloudrun"]
    required_apis = ["monitoring"]
    permissions = [
        *gcp_generic_resource_permissions("monitoring", "uptimeCheckConfigs")
    ]

    def __init__(
        self, name, backend, versioned_clients=None, resources=None, routes_type=None
    ):
        super(Uptime, self).__init__(
            name=name,
            versioned_clients=versioned_clients,
            resources=resources,
            backend=backend,
        )
        self.resources = resources or {}
        self.routes_type = routes_type

    def register(self, name, func, kwargs):
        self.resources[name] = {"func": func, "name": name, "kwargs": kwargs}

    def __call__(self, request, context=None):
        headers = request.headers or {}
        uptime = self.resources[headers["X-Goblet-Uptime-Name"]]
        return uptime["func"]()

    def _deploy(self, source=None, entrypoint=None):
        # TODO: support api gateway

        if self.resources:
            checks = self.list_uptime_checks()
        for name, uptime in self.resources.items():
            uptime_config = {"displayName": f"{self.name}-{name}"}
            if (
                self.backend.resource_type == "cloudrun"
                and not self.routes_type == "apigateway"
            ):
                uptime_config["monitoredResource"] = {
                    "type": "cloud_run_revision",
                    "labels": {
                        "location": "us-central1",
                        "service_name": self.name,
                        "revision_name": "",
                        "configuration_name": "",
                        "project_id": get_default_project(),
                    },
                }
                uptime_config["httpCheck"] = {
                    "useSsl": True,
                    "headers": {"X-Goblet-Uptime-Name": uptime["name"]},
                }
            if self.backend.resource_type.startswith("cloudfunction"):
                uptime_config["monitoredResource"] = {
                    "type": "uptime_url",
                    "labels": {
                        "host": f"{get_default_location()}-{get_default_project()}.cloudfunctions.net",
                        "project_id": get_default_project(),
                    },
                }
                uptime_config["httpCheck"] = {
                    "useSsl": True,
                    "path": f"/{self.name}",
                    "headers": {"X-Goblet-Uptime-Name": uptime["name"]},
                }

            # update config based on user arguments
            uptime_config = nested_update(uptime_config, uptime["kwargs"])

            # Uptime exists
            check = [
                check
                for check in checks
                if check["displayName"] == uptime_config["displayName"]
            ]
            if len(check) == 1:
                # Setup update mask
                keys = list(uptime_config.keys())

                # Remove keys that cannot be updated
                keys.remove("monitoredResource")
                updateMask = ",".join(keys)

                self.versioned_clients.monitoring_uptime.execute(
                    "patch",
                    parent_key="name",
                    parent_schema=check[0]["name"],
                    params={"body": uptime_config, "updateMask": updateMask},
                )
                log.info(f"updated uptime check: {name} for {self.name}")

            else:
                self.versioned_clients.monitoring_uptime.execute(
                    "create", params={"body": uptime_config}
                )
                log.info(f"created uptime check: {name} for {self.name}")

        return

    def destroy(self):
        if not self.resources:
            return
        for check in self.list_uptime_checks():
            self._destroy_uptime_check(check)

    def _destroy_uptime_check(self, check):
        try:
            self.versioned_clients.monitoring_uptime.execute(
                "delete", parent_key="name", parent_schema=check["name"]
            )
            log.info(f"Destroying uptime check {check['displayName']}......")
        except HttpError as e:
            if e.resp.status == 404:
                log.info("Uptime check already destroyed")
            else:
                raise e

    def list_uptime_checks(self):
        resp = self.versioned_clients.monitoring_uptime.execute(
            "list",
            parent_key="parent",
            params={"filter": f"displayName=starts_with('{self.name}-')"},
        )
        return resp.get("uptimeCheckConfigs", [])

    def set_invoker_permissions(self):
        return
