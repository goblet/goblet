from goblet.common_cloud_actions import (
    create_eventarc_trigger,
    destroy_eventarc_trigger,
    get_cloudrun_url,
)

from goblet.config import GConfig
import logging

from goblet.handler import Handler
from goblet.client import get_default_project, get_default_location

log = logging.getLogger("goblet.deployer")
log.setLevel(logging.INFO)


class EventArc(Handler):
    """Eventarc trigger
    https://cloud.google.com/eventarc/docs
    """

    resource_type = "eventarc"
    # Cloudfunctions gen 2 is also supported
    valid_backends = ["cloudrun"]

    def __init__(
        self, name, versioned_clients=None, resources=None, backend="cloudfunction"
    ):
        super(EventArc, self).__init__(
            name,
            versioned_clients=versioned_clients,
            resources=resources,
            backend=backend,
        )
        self.resources = resources or []

    def register_trigger(self, name, func, kwargs):
        event_filters = kwargs.get("event_filters")
        if kwargs.get("topic"):
            event_filters = [
                {
                    "attribute": "type",
                    "value": "google.cloud.pubsub.topic.v1.messagePublished",
                }
            ]
        self.resources.append(
            {
                "trigger_name": f"{self.name}-{name}",
                "event_filters": event_filters,
                "topic": f"projects/{get_default_project()}/topics/{kwargs['topic']}",
                "name": name,
                "func": func,
            }
        )

    def __call__(self, event, context):
        event_type = context.event_type
        # todo
        matched_triggers = [
            t for t in self.resources if t["event_filters"]["value"] == event_type
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
        if not self.resources:
            return
        cloudrun_url = get_cloudrun_url(self.versioned_clients.run, self.name)
        gconfig = GConfig(config=config)
        if gconfig.eventarc and gconfig.eventarc.get("serviceAccount"):
            service_account = gconfig.eventarc.get("serviceAccount")
        elif gconfig.cloudrun and gconfig.cloudrun.get("service-account"):
            service_account = gconfig.cloudrun.get("service-account")
        else:
            raise ValueError(
                "Service account not found for cloudrun or eventarc. You can set `serviceAccount` field in config.json under `eventarc`"
            )

        log.info("deploying eventarc triggers......")
        for trigger in self.resources:
            topic = {}
            if trigger.get("topic"):
                topic = {"transport": {"pubsub": {"topic": trigger.get("topic")}}}
            req_body = {
                "name": f"projects/{get_default_project()}/locations/{get_default_location()}/triggers/{trigger['trigger_name']}",
                "eventFilters": trigger["event_filters"],
                "serviceAccount": service_account,
                "destination": {
                    "cloudRun": {
                        "service": cloudrun_url, "region": get_default_location()
                    }
                },
                **topic
            }

            create_eventarc_trigger(self.versioned_clients.eventarc, trigger['trigger_name'], req_body)

    def destroy(self):
        for trigger in self.resources:
            destroy_eventarc_trigger(self.versioned_clients.eventarc, trigger["trigger_name"])
