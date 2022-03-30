from goblet.common_cloud_actions import (
    create_eventarc_trigger,
    destroy_eventarc_trigger,
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
        region = kwargs.get("kwargs", {}).get("region", get_default_location())
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
                "topic": kwargs["topic"],
                "region": region,
                "name": name,
                "func": func,
            }
        )

    def __call__(self, request):
        # Ce-Source: //pubsub.googleapis.com/projects/premise-governance-rd/topics/test
        # Ce-Type: google.cloud.pubsub.topic.v1.messagePublished
        headers = request.headers
        # todo
        matched_triggers = [
            t
            for t in self.resources
            if self.match_event_filters(headers, t["event_filters"])
        ]
        if not matched_triggers:
            raise ValueError("No triggers found")
        for t in matched_triggers:
            t["func"](request)

        return

    def match_event_filters(self, headers, event_filters):
        for filter in event_filters:
            key = f"Ce-{filter['attribute'].capitalize()}"
            value = filter["value"]
            if not headers.get(key) == value:
                return False
        return True

    def __add__(self, other):
        self.resources.extend(other.resources)
        return self

    def _deploy(self, sourceUrl=None, entrypoint=None, config={}):
        if not self.resources:
            return
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
                topic = {
                    "transport": {
                        "pubsub": {
                            "topic": f"projects/{get_default_project()}/topics/{trigger.get('topic')}"
                        }
                    }
                }
            req_body = {
                "name": f"projects/{get_default_project()}/locations/{trigger['region']}/triggers/{trigger['trigger_name']}",
                "eventFilters": trigger["event_filters"],
                "serviceAccount": service_account,
                "destination": {
                    "cloudRun": {"service": self.name, "region": get_default_location()}
                },
                **topic,
            }
            create_eventarc_trigger(
                self.versioned_clients.eventarc,
                trigger["trigger_name"],
                trigger["region"],
                req_body,
            )

    def destroy(self):
        for trigger in self.resources:
            destroy_eventarc_trigger(
                self.versioned_clients.eventarc, trigger["trigger_name"]
            )
