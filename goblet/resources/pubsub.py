import base64
from goblet.common_cloud_actions import (
    create_pubsub_subscription,
    destroy_pubsub_subscription,
    get_cloudrun_url,
)
from goblet.deploy import create_cloudfunction, destroy_cloudfunction

from goblet.config import GConfig
import logging

from goblet.handler import Handler
from goblet.client import get_default_project, get_default_location


log = logging.getLogger("goblet.deployer")
log.setLevel(logging.INFO)


class PubSub(Handler):
    """Pubsub topic trigger
    https://cloud.google.com/functions/docs/calling/pubsub
    """

    valid_backends = ["cloudfunction", "cloudrun"]
    resource_type = "pubsub"

    def __init__(self, name, resources=None, backend="cloudfunction"):
        self.name = name
        self.backend = backend
        self.cloudfunction = f"projects/{get_default_project()}/locations/{get_default_location()}/functions/{name}"
        self.resources = resources or {}

    def register_topic(self, name, func, kwargs):
        topic = kwargs["topic"]
        kwargs = kwargs.pop("kwargs")
        attributes = kwargs.get("attributes", {})
        if self.resources.get(topic):
            self.resources[topic][name] = {"func": func, "attributes": attributes}
        else:
            self.resources[topic] = {name: {"func": func, "attributes": attributes}}

    def __call__(self, event, context):
        topic_name = context.resource.split("/")[-1]
        data = base64.b64decode(event["data"]).decode("utf-8")
        attributes = event.get("attributes") or {}

        topic = self.resources.get(topic_name)
        if not topic:
            raise ValueError(f"Topic {topic_name} not found")

        # check attributes
        for name, info in topic.items():
            if info["attributes"].items() <= attributes.items():
                info["func"](data)
        return

    def _deploy(self, sourceUrl=None, entrypoint=None, config={}):
        if not self.resources:
            return
        if self.backend == "cloudfunction":
            self._deploy_cloudfunction(sourceUrl=sourceUrl, entrypoint=entrypoint)
        if self.backend == "cloudrun":
            self._deploy_cloudrun(config=config)

    def _deploy_cloudrun(self, config={}):
        log.info("deploying pubsub subscriptions......")
        push_url = get_cloudrun_url(self.name)

        config = GConfig(config=config)
        if config.cloudrun and config.cloudrun.get("service-account"):
            service_account = config.cloudrun.get("service-account")
        elif config.pubsub and config.pubsub.get("serviceAccountEmail"):
            service_account = config.pubsub.get("serviceAccountEmail")
        else:
            raise ValueError(
                "Service account not found in cloudrun. You can set `serviceAccountEmail` field in config.json under `pubsub`"
            )

        for topic in self.resources:
            sub_name = f"{self.name}-{topic}"
            req_body = {
                "name": sub_name,
                "topic": f"projects/{get_default_project()}/topics/{topic}",
                "pushConfig": {
                    "pushEndpoint": push_url,
                    "oidcToken": {
                        "serviceAccountEmail": service_account,
                        "audience": push_url,
                    },
                },
            }
            create_pubsub_subscription(sub_name=sub_name, req_body=req_body)

    def _deploy_cloudfunction(self, sourceUrl=None, entrypoint=None):
        log.info("deploying topic functions......")
        config = GConfig()
        user_configs = config.cloudfunction or {}
        for topic in self.resources:
            req_body = {
                "name": f"{self.cloudfunction}-topic-{topic}",
                "description": config.description or "created by goblet",
                "entryPoint": entrypoint,
                "sourceUploadUrl": sourceUrl,
                "eventTrigger": {
                    "eventType": "providers/cloud.pubsub/eventTypes/topic.publish",
                    "resource": f"projects/{get_default_project()}/topics/{topic}",
                },
                "runtime": config.runtime or "python37",
                **user_configs,
            }
            create_cloudfunction(req_body)

    def destroy(self):
        if self.backend == "cloudfunction":
            for topic in self.resources:
                destroy_cloudfunction(f"{self.name}-topic-{topic}")
        if self.backend == "cloudrun":
            for topic in self.resources:
                destroy_pubsub_subscription(f"{self.name}-{topic}")
