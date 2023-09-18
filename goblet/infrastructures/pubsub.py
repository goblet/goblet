import json
import logging
from base64 import b64encode
from googleapiclient.errors import HttpError
from goblet.infrastructures.infrastructure import Infrastructure
from goblet.client import VersionedClients
from goblet.permissions import gcp_generic_resource_permissions, add_binding
from goblet.client import get_default_project_number
from goblet.common_cloud_actions import (
    create_pubsub_subscription,
    destroy_pubsub_subscription,
)

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
    supports_local = True

    def register(self, name, kwargs):
        resource_id = name
        topic_config = kwargs.get("config", None)
        dlq = kwargs.get("dlq", False)
        dlq_pull_subscription = kwargs.get("dlq_pull_subscription", None)

        self.resources[resource_id] = {
            "id": resource_id,
            "name": f"{self.versioned_clients.pubsub_topic.parent}/topics/{name}",
            "config": topic_config,
            "dlq": dlq,
            "dlq_pull_subscription": dlq_pull_subscription,
        }
        return PubSubClient(topic=self.resources[resource_id]["name"])

    def _deploy(self):
        if not self.resources:
            return

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

                if resource["dlq"] is True:
                    # Add IAM roles to use dead-letter topics
                    try:
                        default_pubsub_service_account = f"serviceAccount:service-{get_default_project_number()}@gcp-sa-pubsub.iam.gserviceaccount.com"
                        add_binding(
                            self.versioned_clients.pubsub_topic,
                            resource["name"],
                            "roles/pubsub.publisher",
                            default_pubsub_service_account,
                        )
                    except HttpError as e:
                        if e.resp.status == 403:
                            log.info(
                                f"User is not authorized to add IAM role 'roles/pubsub.publisher' to topic '{resource['name']}' you need to handle this manually."
                            )

                    # Create Pull Subscription for DLQ so messages don't get lost
                    dlq_pull_subscription = resource["dlq_pull_subscription"]
                    log.info(
                        f"Creating pull subscription {dlq_pull_subscription['name']} for DLQ {resource['id']}"
                    )
                    create_pubsub_subscription(
                        client=self.versioned_clients.pubsub,
                        sub_name=dlq_pull_subscription["name"],
                        force_update=False,
                        req_body={
                            "name": dlq_pull_subscription["name"],
                            "topic": resource["name"],
                            **dlq_pull_subscription.get("config", {}),
                        },
                    )

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
                if resource["dlq"] is True:
                    # Delete Pull Subscription for DLQ
                    dlq_pull_subscription = resource["dlq_pull_subscription"]
                    log.info(
                        f"Deleting pull subscription {dlq_pull_subscription['name']} for DLQ {resource['id']}"
                    )
                    destroy_pubsub_subscription(
                        self.versioned_clients.pubsub, dlq_pull_subscription["name"]
                    )

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
