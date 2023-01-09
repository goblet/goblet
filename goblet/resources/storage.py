from goblet.config import GConfig
import logging

from goblet.resources.handler import Handler
from goblet.client import get_default_project, get_default_location
from goblet.common_cloud_actions import (
    get_function_runtime,
    create_cloudfunctionv2,
    create_cloudfunctionv1,
    destroy_cloudfunction,
)

log = logging.getLogger("goblet.deployer")
log.setLevel(logging.INFO)

STORAGE_EVENT_TYPES = {
    "v1": ["finalize", "delete", "archive", "metadataUpdate"],
    "v2": ["finalized", "deleted", "archived", "metadataUpdated"],
}


class Storage(Handler):
    """Storage trigger
    https://cloud.google.com/functions/docs/calling/storage
    """

    resource_type = "storage"
    valid_backends = ["cloudfunction", "cloudfunctionv2"]

    def __init__(self, name, backend, versioned_clients=None, resources=None):
        super(Storage, self).__init__(
            name,
            versioned_clients=versioned_clients,
            resources=resources,
            backend=backend,
        )
        self.resources = resources or []
        self.cloudfunction = f"projects/{get_default_project()}/locations/{get_default_location()}/functions/{name}"

    def validate_event_type(self, event_type):
        gcf_version = self.versioned_clients.cloudfunctions.version[:2]
        if event_type not in STORAGE_EVENT_TYPES[gcf_version]:
            raise ValueError(
                f"{event_type} not in {STORAGE_EVENT_TYPES[gcf_version]}. See https://cloud.google.com/functions/docs"
                f"/calling/storage for more information. "
            )

    def register(self, name, func, kwargs):
        bucket_name = kwargs["bucket"]
        event_type = kwargs["event_type"]
        self.validate_event_type(event_type)
        self.resources.append(
            {
                "bucket": bucket_name,
                "event_type": event_type,
                "name": name,
                "func": func,
            }
        )

    def __call__(self, event, context):
        event_type = context.event_type.split(".")[-1]
        bucket_name = event["bucket"]

        matched_buckets = [
            b
            for b in self.resources
            if b["bucket"] == bucket_name and b["event_type"][:6] == event_type[:6]
        ]
        if not matched_buckets:
            raise ValueError("No functions found")
        for b in matched_buckets:
            b["func"](event)

        return

    def __add__(self, other):
        self.resources.extend(other.resources)
        return self

    def _deploy(self, source=None, entrypoint=None, config={}):
        client = self.versioned_clients.cloudfunctions
        if not self.resources or not source:
            return

        log.info("deploying storage functions......")
        gconfig = GConfig(config)
        user_configs = gconfig.cloudfunction or {}
        for bucket in self.resources:
            function_name = f"{self.cloudfunction}-storage-{bucket['name']}-{bucket['event_type']}".replace(
                ".", "-"
            )
            if self.versioned_clients.cloudfunctions.version == "v1":
                req_body = {
                    "name": function_name,
                    "description": gconfig.description or "created by goblet",
                    "entryPoint": entrypoint,
                    "sourceUploadUrl": source["uploadUrl"],
                    "eventTrigger": {
                        "eventType": f"google.storage.object.{bucket['event_type']}",
                        "resource": f"projects/{get_default_project()}/buckets/{bucket['bucket']}",
                    },
                    "runtime": get_function_runtime(client, gconfig),
                    "labels": gconfig.labels,
                    **user_configs,
                }
                create_cloudfunctionv1(
                    self.versioned_clients.cloudfunctions, {"body": req_body}
                )
            elif self.versioned_clients.cloudfunctions.version.startswith("v2"):
                params = {
                    "body": {
                        "name": function_name,
                        "environment": "GEN_2",
                        "description": config.description or "created by goblet",
                        "buildConfig": {
                            "runtime": get_function_runtime(client, gconfig),
                            "entryPoint": entrypoint,
                            "source": {"storageSource": source["storageSource"]},
                        },
                        "eventTrigger": {
                            "eventType": f"google.cloud.storage.object.v1.{bucket['event_type']}",
                            "eventFilters": [
                                {
                                    "attribute": "bucket",
                                    "value": bucket["bucket"],
                                }
                            ],
                        },
                        **user_configs,
                    },
                    "labels": gconfig.labels,
                    "functionId": function_name.split("/")[-1],
                }
                create_cloudfunctionv2(self.versioned_clients.cloudfunctions, params)
            else:
                raise

    def destroy(self):
        for bucket in self.resources:
            destroy_cloudfunction(
                self.versioned_clients.cloudfunctions,
                f"{self.name}-storage-{bucket['name']}-{bucket['event_type']}".replace(
                    ".", "-"
                ),
            )
