import base64
from goblet.deploy import create_cloudfunction, destroy_cloudfunction

from goblet.config import GConfig
import logging

from goblet.handler import Handler
from goblet.client import get_default_project, get_default_location


log = logging.getLogger('goblet.deployer')
log.setLevel(logging.INFO)


class PubSub(Handler):
    """Pubsub topic trigger
    https://cloud.google.com/functions/docs/calling/pubsub
    """

    valid_backends = ["cloudfunction", "cloudrun"]
    resource_type = "pubsub"

    def __init__(self, name, resources=None):
        self.name = name
        self.cloudfunction = f"projects/{get_default_project()}/locations/{get_default_location()}/functions/{name}"
        self.resources = resources or {}

    def register_topic(self, name, func, kwargs):
        topic = kwargs["topic"]
        kwargs = kwargs.pop('kwargs')
        attributes = kwargs.get("attributes", {})
        if self.resources.get(topic):
            self.resources[topic][name] = {
                "func": func,
                "attributes": attributes
            }
        else:
            self.resources[topic] = {
                name: {
                    "func": func,
                    "attributes": attributes
                }
            }

    def __call__(self, event, context):
        topic_name = context.resource.split('/')[-1]
        data = base64.b64decode(event['data']).decode('utf-8')
        attributes = event.get("attributes") or {}

        topic = self.resources.get(topic_name)
        if not topic:
            raise ValueError(f"Topic {topic_name} not found")

        # check attributes
        for name, info in topic.items():
            if info["attributes"].items() <= attributes.items():
                info["func"](data)
        return

    def _deploy(self, sourceUrl=None, entrypoint=None, backend="cloudfunction"):
        if not self.resources:
            return

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
                    "resource": f"projects/{get_default_project()}/topics/{topic}"
                },
                "runtime": config.runtime or "python37",
                **user_configs
            }
            create_cloudfunction(req_body)

    def destroy(self):
        for topic in self.resources:
            destroy_cloudfunction(f"{self.name}-topic-{topic}")
