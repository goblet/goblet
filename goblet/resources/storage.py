import base64
from goblet.deploy import create_cloudfunction, destroy_cloudfunction

from goblet.config import GConfig
import logging

from goblet.handler import Handler
from goblet.client import get_default_project, get_default_location


log = logging.getLogger('goblet.deployer')
log.setLevel(logging.INFO)

STORAGE_EVENT_TYPES = [
    "finalize",
    "delete",
    "archive",
    "metadataUpdate"
]
class Storage(Handler):
    def __init__(self, name, buckets=None):
        self.name = name
        self.cloudfunction = f"projects/{get_default_project()}/locations/{get_default_location()}/functions/{name}"
        self.buckets = buckets or {}

    def validate_event_type(self, event_type):
        if event_type not in STORAGE_EVENT_TYPES:
            raise ValueError(f"{event_type} not in {STORAGE_EVENT_TYPES}")

    def register_bucket(self, name, func, kwargs):
        bucket = kwargs["bucket"]
        event_type = kwargs["event_type"]
        self.validate_event_type(event_type)
        key = f"{bucket}-{event_type}"
        if self.buckets.get(key):
            # TODO: mulitple functions can be triggered on same event?
        self.buckets[] = {
            "bucket": bucket,
            "event_type": event_type,
            "name": name,
            "func": func
        }

    def __call__(self, event, context):
        event_type = context.event_type.split('.')[-1]
        bucket_name = event['bucket']

        buckets = [b for b in self.buckets if b.startswith(f"{bucket_name}-{event_type}")
        if not buckets:
            raise ValueError("No functions found")
        for key in buckets:
            self.buckets[key]["func"](event)

        return

    def __add__(self, other):
        self.buckets.update(other.buckets)
        return self

    def deploy(self, sourceUrl=None, entrypoint=None):
        if not self.buckets:
            return

        log.info("deploying storage functions......")
        config = GConfig()
        user_configs = config.cloudfunction or {}
        for key, bucket in self.buckets.items():
            req_body = {
                "name": f"{self.cloudfunction}-storage-{key}",
                "description": config.description or "created by goblet",
                "entryPoint": entrypoint,
                "sourceUploadUrl": sourceUrl,
                "eventTrigger": {
                    "eventType": f"providers/cloud.storage/eventTypes/google.storage.object.{bucket["event_type"]}",
                    "resource": bucket["bucket"]
                },
                "runtime": config.runtime or "python37",
                **user_configs
            }
            create_cloudfunction(req_body)

    def destroy(self):
        for key in self.buckets:
            destroy_cloudfunction(f"{self.cloudfunction}-storage-{key}")
