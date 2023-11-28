from goblet.handlers.handler import Handler
from goblet.permissions import gcp_generic_resource_permissions
from goblet.utils import nested_update
from goblet_gcp_client.client import get_default_project


class Uptime(Handler):
    """Uptime Trigger"""

    resource_type = "uptime"
    valid_backends = ["cloudfunction", "cloudfunctionv2", "cloudrun"]
    # can_sync = True
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
        self.resources = resources or []
        self.routes_type = routes_type

    def register(self, name, func, kwargs):
        self.resources[name] = {"func": func, "name": name, "kwargs": kwargs}

    def __call__(self, request, context=None):
        headers = request.headers or {}
        uptime = self.resources[headers["X-Goblet-Uptime-Name"]]
        return uptime["func"]()

    def _deploy(self, source=None, entrypoint=None):
        for name, uptime in self.resources.items():
            if (
                self.backend.resource_type == "cloudrun"
                and not self.routes_type == "apigateway"
            ):
                uptime_config = {"name": name}
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
                uptime_config = nested_update(uptime_config, **uptime["kwargs"])
            # TODO: Deploy/ Patch

        return

    def destroy(self):
        # TODO: Destroy
        return
