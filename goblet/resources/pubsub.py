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
from goblet.client import get_default_project


log = logging.getLogger("goblet.deployer")
log.setLevel(logging.INFO)


class PubSub(Handler):
    """Pubsub topic trigger
    https://cloud.google.com/functions/docs/calling/pubsub
    """

    valid_backends = ["cloudfunction", "cloudrun"]
    resource_type = "pubsub"
    can_sync = True

    def register_topic(self, name, func, kwargs):
        topic = kwargs["topic"]
        kwargs = kwargs.pop("kwargs")
        attributes = kwargs.get("attributes", {})
        project = kwargs.get("project")
        use_trigger = kwargs.get("use_trigger", True)
        if project:
            user_trigger=False
        if self.resources.get(topic):
            self.resources[topic][name] = {"func": func, "attributes": attributes, "project": project, "use_trigger": use_trigger}
        else:
            self.resources[topic] = {name: {"func": func, "attributes": attributes, "project": project, "use_trigger": use_trigger}}

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
        for topic_name in self.resources:
            # Check if subscription needs to be created. Currently it is not supported to create a trigger and a subscription
            skip_trigger = any([True for topic in self.resources[topic_name].values() if not topic.get("use_trigger") ])
            if self.backend == "cloudrun" or skip_trigger:
                self._deploy_cloudrun(config=config, topic=topic)
            if self.backend == "cloudfunction":
                self._deploy_cloudfunction(sourceUrl=sourceUrl, entrypoint=entrypoint, topic=topic)

    def _deploy_cloudrun(self, topic, config={}):
        sub_name = f"{self.name}-{topic}"
        log.info(f"deploying pubsub subscription {sub_name}......")
        push_url = get_cloudrun_url(self.versioned_clients.run, self.name)

        config = GConfig(config=config)
        if config.cloudrun and config.cloudrun.get("service-account"):
            service_account = config.cloudrun.get("service-account")
        elif config.pubsub and config.pubsub.get("serviceAccountEmail"):
            service_account = config.pubsub.get("serviceAccountEmail")
        else:
            raise ValueError(
                "Service account not found in cloudrun. You can set `serviceAccountEmail` field in config.json under `pubsub`"
            )

        req_body = {
            "name": sub_name,
            "topic": f"projects/{topic['project']}/topics/{topic}",
            "pushConfig": {
                "pushEndpoint": push_url,
                "oidcToken": {
                    "serviceAccountEmail": service_account,
                    "audience": push_url,
                },
            },
        }
        create_pubsub_subscription(
            client=self.versioned_clients.pubsub,
            sub_name=sub_name,
            req_body=req_body,
        )

    def _deploy_cloudfunction(self, topic, sourceUrl=None, entrypoint=None):
        function_name = f"{self.cloudfunction}-topic-{topic}"
        log.info(f"deploying topic function {function_name}......")
        config = GConfig()
        user_configs = config.cloudfunction or {}
        req_body = {
            "name": function_name,
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
        create_cloudfunction(self.versioned_clients.cloudfunctions, req_body)

    def _sync(self, dryrun=False):
        if not self.backend == "cloudrun":
            return
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

    def destroy(self):
        if self.backend == "cloudfunction":
            for topic in self.resources:
                destroy_cloudfunction(
                    self.versioned_clients.cloudfunctions, f"{self.name}-topic-{topic}"
                )
        if self.backend == "cloudrun":
            for topic in self.resources:
                destroy_pubsub_subscription(
                    self.versioned_clients.pubsub, f"{self.name}-{topic}"
                )
