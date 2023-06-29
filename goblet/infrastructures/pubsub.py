import json
from base64 import b64encode
from googleapiclient.errors import HttpError
from goblet.infrastructures.infrastructure import Infrastructure
import logging
from goblet.client import VersionedClients
from goblet.permissions import gcp_generic_resource_permissions

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
                    "messages": [{"data": b64encode(message.encode()).decode("utf8")}]
                }
            },
        )


class PubSubTopic(Infrastructure):
    resource_type = "pubsub_topic"
    required_apis = ["pubsub"]
    permissions = gcp_generic_resource_permissions("pubsub", "topics")

    def register(self, name, kwargs):
        resource_id = name
        topic_config = kwargs.get("config", None)

        self.resources[resource_id] = {
            "id": resource_id,
            "name": f"{self.versioned_clients.pubsub_topic.parent}/topics/{name}",
            "config": topic_config,
        }
        return PubSubClient(topic=self.resources[resource_id]["name"])

    def deploy(self, config={}):
        if not self.resources:
            return
        self.config.update_g_config(values=config)

        for resource_id, resource in self.resources.items():
            params = {"name": resource["name"]}
            if resource["config"]:
                params = {**params, **resource["config"]}

            try:
                self.versioned_clients.pubsub_topic.execute(
                    "create",
                    parent_key="name",
                    parent_schema=resource["name"],
                    params={"body": params},
                )
                log.info(f'PubSub Topic [{resource["id"]}] deployed')

            except HttpError as e:
                if e.resp.status == 409:
                    log.info(f'found pubsub topic {resource["id"]}')
                    updateMask = ",".join(self.paths_to_update(resource_id))
                    if updateMask != "":
                        log.info(f"params: {params}")
                        self.versioned_clients.pubsub_topic.execute(
                            "patch",
                            parent=None,
                            params={
                                "name": self.resources[resource_id]["name"],
                                "body": {"topic": params, "updateMask": updateMask},
                            },
                        )
                        log.info(f"PubSub Topic [{resource['id']}] patched")
                else:
                    raise e

    def destroy(self, config={}):
        if not self.resources:
            return
        for resource_id, resource in self.resources.items():
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

    def paths_to_update(self, resource_id):
        paths = []

        # if there is user config, there is nothing to compare with
        if not self.resources[resource_id].get("config"):
            return paths

        deployed_config = self.get(resource_id)
        for k, v in self.resources[resource_id]["config"].items():
            try:
                # a value set in the desired config is
                # different from the value deployed
                if deployed_config[k] != v:
                    paths.append(k)
            except KeyError:
                paths.append(k)
            except Exception as e:
                raise e

        return paths

    def get(self, resource_id):
        if not self.resources or not resource_id:
            return
        return self.versioned_clients.pubsub_topic.execute(
            "get", parent=None, params={"topic": self.resources[resource_id]["name"]}
        )

    def get_config(self, config={}):
        if not self.resources:
            return

        return {"resource_type": self.resource_type, "values": {}}
