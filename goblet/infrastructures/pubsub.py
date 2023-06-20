import json
from base64 import b64encode
from googleapiclient.errors import HttpError
from goblet.infrastructures.infrastructure import Infrastructure
import logging
from goblet.client import VersionedClients

log = logging.getLogger("goblet.deployer")
log.setLevel(logging.INFO)


class PubSubClient:
    def __init__(self, topic):
        self.topic = topic

    def publish(self, message):
        message = json.dumps(message)
        return VersionedClients().pubsub_topic.execute(
            "publish",
            parent_key="topic",
            parent_schema=self.topic,
            params={
                "body": {
                    "messages": [
                        {
                            "data": b64encode(message.encode()).decode("utf8")
                        }
                    ]
                }
            }
        )


class PubSubTopic(Infrastructure):
    resource_type = "pubsub_topic"

    def register(self, name, kwargs):
        resource_id = name
        topic_config = kwargs.get("config", None)

        self.resource[resource_id] = {
            "id": resource_id,
            "name": f"{self.versioned_clients.pubsub_topic.parent}/topics/{name}",
            "config": topic_config
        }
        return PubSubClient(
            topic=self.resource[resource_id]["name"]
        )

    def deploy(self, config={}):
        if not self.resource:
            return
        self.config.update_g_config(values=config)

        for resource_id, resource in self.resource.items():
            params = {"name": resource["name"]}
            if resource["config"]:
                params = {**params, **resource["config"]}

            try:
                self.versioned_clients.pubsub_topic.execute(
                    "create",
                    parent_key="name",
                    parent_schema=resource["name"],
                    params={"body": params}
                )
                log.info(f'PubSub Topic [{resource["id"]}] deployed')

            except HttpError as e:
                if e.resp.status == 409:
                    log.info(f'found pubsub topic {resource["id"]}')
                else:
                    raise e

    def destroy(self, config={}):
        if not self.resource:
            return
        for resource_id, resource in self.resource.items():
            try:
                resp = self.versioned_clients.pubsub_topic.execute(
                    "delete", parent_key="topic", parent_schema=resource["name"]
                )
                if resp == {}:
                    log.info(f"PubSub Topic [{resource['id']}] destroyed")
            except HttpError as e:
                if e.resp.status == 404:
                    log.info(f"PubSub Topic {resource['id']} already destroyed")
                else:
                    raise e

    def get(self, resource_id):
        if not self.resource or not resource_id:
            return
        return self.versioned_clients.pubsub_topic.execute(
            "get", parent_key="name", parent_schema=self.resource[resource_id]["name"]
        )

    def get_config(self, config={}):
        if not self.resource:
            return

        return {"resource_type": self.resource_type, "values": {}}
