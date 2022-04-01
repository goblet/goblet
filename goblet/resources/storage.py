from goblet.deploy import create_cloudfunction, destroy_cloudfunction

from goblet.config import GConfig
import logging

from goblet.handler import Handler
from goblet.client import get_default_project, get_default_location

log = logging.getLogger("goblet.deployer")
log.setLevel(logging.INFO)

STORAGE_EVENT_TYPES = ["finalize", "delete", "archive", "metadataUpdate"]


class Storage(Handler):
    """Storage trigger
    https://cloud.google.com/functions/docs/calling/storage
    """

    resource_type = "storage"
    valid_backends = ["cloudfunction"]

    def __init__(
        self, name, versioned_clients=None, resources=None, backend="cloudfunction"
    ):
        super(Storage, self).__init__(
            name,
            versioned_clients=versioned_clients,
            resources=resources,
            backend=backend,
        )
        self.resources = resources or []
        self.cloudfunction = f"projects/{get_default_project()}/locations/{get_default_location()}/functions/{name}"

    def validate_event_type(self, event_type):
        if event_type not in STORAGE_EVENT_TYPES:
            raise ValueError(f"{event_type} not in {STORAGE_EVENT_TYPES}")

    def register_bucket(self, name, func, kwargs):
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
            if b["bucket"] == bucket_name and b["event_type"] == event_type
        ]
        if not matched_buckets:
            raise ValueError("No functions found")
        for b in matched_buckets:
            b["func"](event)

        return

    def __add__(self, other):
        self.resources.extend(other.resources)
        return self

    def _deploy(self, sourceUrl=None, entrypoint=None, config={}):
        if not self.resources or not sourceUrl:
            return

        log.info("deploying storage functions......")
        config = GConfig()
        user_configs = config.cloudfunction or {}
        for bucket in self.resources:
            req_body = {
                "name": f"{self.cloudfunction}-storage-{bucket['name']}-{bucket['event_type']}".replace(
                    ".", "-"
                ),
                "description": config.description or "created by goblet",
                "entryPoint": entrypoint,
                "sourceUploadUrl": sourceUrl,
                "eventTrigger": {
                    "eventType": f"google.storage.object.{bucket['event_type']}",
                    "resource": f"projects/{get_default_project()}/buckets/{bucket['bucket']}",
                },
                "runtime": config.runtime or "python37",
                **user_configs,
            }
            create_cloudfunction(self.versioned_clients.cloudfunctions, req_body)

    def destroy(self):
        for bucket in self.resources:
            destroy_cloudfunction(
                self.versioned_clients.cloudfunctions,
                f"{self.name}-storage-{bucket['name']}-{bucket['event_type']}".replace(
                    ".", "-"
                ),
            )
