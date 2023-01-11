import base64
from goblet.common_cloud_actions import (
    create_pubsub_subscription,
    destroy_pubsub_subscription,
    get_function_runtime,
    create_cloudfunctionv2,
    create_cloudfunctionv1,
    destroy_cloudfunction,
)

from goblet.config import GConfig
import logging

from goblet.resources.handler import Handler
from goblet.client import get_default_project
from goblet.utils import attributes_to_filter

log = logging.getLogger("goblet.deployer")
log.setLevel(logging.INFO)


class PubSub(Handler):
    """Pubsub topic trigger
    https://cloud.google.com/functions/docs/calling/pubsub
    """

    valid_backends = ["cloudfunction", "cloudfunctionv2", "cloudrun"]
    resource_type = "pubsub"
    can_sync = True

    def register(self, name, func, kwargs):
        topic = kwargs["topic"]
        kwargs = kwargs.pop("kwargs")
        attributes = kwargs.get("attributes", {})
        config = kwargs.get("config", {})
        filter = kwargs.get("filter")
        if not filter and attributes:
            filter = attributes_to_filter(attributes)
        project = kwargs.get("project", get_default_project())
        deploy_type = "trigger"
        if (
            kwargs.get("use_subscription")
            or project != get_default_project()
            or self.backend.resource_type == "cloudrun"
        ):
            deploy_type = "subscription"

        if self.resources.get(topic):
            self.resources[topic][deploy_type][name] = {
                "func": func,
                "attributes": attributes,
                "project": project,
                "filter": filter,
            }
        else:
            self.resources[topic] = {"trigger": {}, "subscription": {}}
            self.resources[topic][deploy_type] = {
                name: {
                    "func": func,
                    "attributes": attributes,
                    "project": project,
                    "filter": filter,
                    "config": config,
                }
            }

    def __call__(self, event, context):
        # Trigger
        if context:
            try:
                topic_name = context.resource.split("/")[-1]
            except AttributeError:
                topic_name = context.resource["name"].split("/")[-1]
            data = base64.b64decode(event["data"]).decode("utf-8")
            attributes = event.get("attributes") or {}
        # Subscription
        else:
            subscription = event.json["subscription"].split("/")[-1]
            topic_name = subscription.replace(self.name + "-", "")
            data = base64.b64decode(event.json["message"]["data"]).decode("utf-8")
            attributes = event.json["message"].get("attributes") or {}

        topic = self.resources.get(topic_name)
        if not topic:
            raise ValueError(f"Topic {topic_name} not found")

        # check attributes
        response = None
        for _, info in topic["trigger"].items():
            if info["attributes"].items() <= attributes.items():
                response = info["func"](data)
        for _, info in topic["subscription"].items():
            if info["attributes"].items() <= attributes.items():
                response = info["func"](data)
        return response or "success"

    def _deploy(self, source=None, entrypoint=None, config={}):
        if not self.resources:
            return
        for topic_name in self.resources:
            # Deploy triggers
            for _, topic_info in self.resources[topic_name]["trigger"].items():
                self._deploy_trigger(
                    source=source, entrypoint=entrypoint, topic_name=topic_name
                )
            # Deploy subscriptions
            for _, topic_info in self.resources[topic_name]["subscription"].items():
                self._deploy_subscription(
                    config=config, topic_name=topic_name, topic=topic_info
                )

    def _deploy_subscription(self, topic_name, topic, config={}):
        sub_name = f"{self.name}-{topic_name}"
        log.info(f"deploying pubsub subscription {sub_name}......")

        push_url = self.backend.http_endpoint

        gconfig = GConfig(config=config)
        if gconfig.pubsub and gconfig.pubsub.get("serviceAccountEmail"):
            service_account = gconfig.pubsub.get("serviceAccountEmail")
        elif (
            self.backend.resource_type == "cloudrun"
            and gconfig.cloudrun_revision
            and gconfig.cloudrun_revision.get("serviceAccount")
        ):
            service_account = gconfig.cloudrun_revision.get("serviceAccount")
        elif (
            self.backend.resource_type.startswith("cloudfunction")
            and gconfig.cloudfunction
            and gconfig.pubsub.get("serviceAccountEmail")
        ):
            service_account = gconfig.pubsub.get("serviceAccountEmail")
        else:
            raise ValueError(
                "Service account not found in cloudrun or cloudfunction. You can set `serviceAccountEmail` field in config.json under `pubsub`"
            )
        req_body = {
            "name": sub_name,
            "topic": f"projects/{topic['project']}/topics/{topic_name}",
            "filter": topic["filter"] or "",
            "pushConfig": {}
            if topic["config"].get("enableExactlyOnceDelivery", None)
            else {
                "pushEndpoint": push_url,
                "oidcToken": {
                    "serviceAccountEmail": service_account,
                    "audience": push_url,
                },
            },
            "labels": gconfig.labels,
            **topic["config"],
        }
        create_pubsub_subscription(
            client=self.versioned_clients.pubsub,
            sub_name=sub_name,
            req_body=req_body,
        )

    def _deploy_trigger(self, topic_name, source=None, entrypoint=None):
        function_name = f"{self.cloudfunction}-topic-{topic_name}"
        log.info(f"deploying topic function {function_name}......")
        gconfig = GConfig()
        user_configs = gconfig.cloudfunction or {}
        if self.versioned_clients.cloudfunctions.version == "v1":
            req_body = {
                "name": function_name,
                "description": gconfig.description or "created by goblet",
                "entryPoint": entrypoint,
                "sourceUploadUrl": source["uploadUrl"],
                "eventTrigger": {
                    "eventType": "providers/cloud.pubsub/eventTypes/topic.publish",
                    "resource": f"projects/{get_default_project()}/topics/{topic_name}",
                },
                "runtime": get_function_runtime(
                    self.versioned_clients.cloudfunctions, gconfig
                ),
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
                    "description": gconfig.description or "created by goblet",
                    "buildConfig": {
                        "runtime": get_function_runtime(
                            self.versioned_clients.cloudfunctions, gconfig
                        ),
                        "entryPoint": entrypoint,
                        "source": {"storageSource": source["storageSource"]},
                    },
                    "eventTrigger": {
                        "eventType": "google.cloud.pubsub.topic.v1.messagePublished",
                        "pubsubTopic": f"projects/{get_default_project()}/topics/{topic_name}",
                    },
                    "labels": gconfig.labels,
                    **user_configs,
                },
                "functionId": function_name.split("/")[-1],
            }
            create_cloudfunctionv2(self.versioned_clients.cloudfunctions, params)
        else:
            raise

    def _sync(self, dryrun=False):
        subscriptions = self.versioned_clients.pubsub.execute(
            "list", parent_key="project"
        ).get("subscriptions", [])
        filtered_subscriptions = list(
            filter(
                lambda sub: f"subscriptions/{self.name}-" in sub["name"], subscriptions
            )
        )

        for filtered_sub in filtered_subscriptions:
            split_name = filtered_sub["name"].split("/")[-1].split("-")
            filtered_name = split_name[1]
            if not self.resources.get(filtered_name):
                log.info(f'Detected unused subscription in GCP {filtered_sub["name"]}')
                if not dryrun:
                    destroy_pubsub_subscription(
                        self.versioned_clients.pubsub, f"{self.name}-{filtered_name}"
                    )

    def is_http(self):
        """
        Http cloudfunction is needed for cloudfunction subscription
        """
        for _, topic_info in self.resources.items():
            if topic_info.get("subscription"):
                return True
        return False

    def destroy(self):
        if not self.resources:
            return
        for topic_name in self.resources:
            # Destroy triggers
            for _, topic_info in self.resources[topic_name]["trigger"].items():
                destroy_cloudfunction(
                    self.versioned_clients.cloudfunctions,
                    f"{self.name}-topic-{topic_name}",
                )
            # Destroy subscriptions
            for _, topic_info in self.resources[topic_name]["subscription"].items():
                destroy_pubsub_subscription(
                    self.versioned_clients.pubsub, f"{self.name}-{topic_name}"
                )
