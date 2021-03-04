import base64
from goblet.deploy import create_cloudfunction, destroy_cloudfunction

from goblet.config import GConfig
import logging

from goblet.handler import Handler
from goblet.client import Client, get_default_project, get_default_location


log = logging.getLogger('goblet.deployer')
log.setLevel(logging.INFO)


class PubSub(Handler):
    def __init__(self, name, topics=None):
        self.name = name
        self.cloudfunction = f"projects/{get_default_project()}/locations/{get_default_location()}/functions/{name}"
        self.topics = topics or {}

    def register_topic(self, name, func, kwargs):
        topic = kwargs["topic"]
        kwargs = kwargs.pop('kwargs')
        attributes = kwargs.get("attributes", {})
        if self.topics.get(topic):
            self.topics[topic][name] = {
                "func": func,
                "attributes": attributes
            }
        else:
            self.topics[topic] = {
                name: {
                    "func": func,
                    "attributes": attributes
                }
            }

    def __call__(self, event, context):
        topic_name = context.resource["name"].split('/')[-1]
        data = base64.b64decode(event['data']).decode('utf-8')
        attributes = event.get("attributes", {})

        topic = self.topics.get(topic_name)
        if not topic:
            raise ValueError(f"Topic {topic_name} not found")

        # check attributes
        for name, info in topic.items():
            if info["attributes"].items() >= attributes:
                topic["func"][name](data)
        return

    def __add__(self, other):
        self.topics.update(other.topics)
        return self

    def deploy(self):
        if not self.topics:
            return

        cloudfunction_client = Client("cloudfunctions", 'v1', calls='projects.locations.functions', parent_schema='projects/{project_id}/locations/{location_id}')
        resp = cloudfunction_client.execute('get', parent_key="name", parent_schema=self.cloudfunction)
        if not resp:
            raise ValueError(f"Function {self.cloudfunction} not found")

        log.info("deploying topic functions......")
        config = GConfig()
        user_configs = config.cloudfunction or {}
        for topic in self.topics:
            req_body = {
                "name": f"{self.cloudfunction}-topic-{topic}",
                "description": config.description or "created by goblet",
                "entryPoint": resp["entrypoint"],
                "sourceUploadUrl": resp["sourceUploadUrl"],
                "eventTrigger": {
                    "eventType": "providers/cloud.pubsub/eventTypes/topic.publish",
                    "resource": f"projects/{get_default_project()}/topics/{topic}"
                },
                "runtime": config.runtime or "python37",
                **user_configs
            }
            create_cloudfunction(req_body)

    def destroy(self):
        for topic in self.topics:
            destroy_cloudfunction(f"{self.cloudfunction}-topic-{topic}")
