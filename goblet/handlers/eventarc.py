from goblet.common_cloud_actions import (
    create_eventarc_trigger,
    destroy_eventarc_trigger,
)
from goblet.response import Response
import logging
import os

from goblet.handlers.handler import Handler
from goblet_gcp_client.client import get_default_project, get_default_location
from goblet.permissions import gcp_generic_resource_permissions

log = logging.getLogger("goblet.deployer")
log.setLevel(logging.getLevelName(os.getenv("GOBLET_LOG_LEVEL", "INFO")))


class EventArc(Handler):
    """Eventarc trigger
    https://cloud.google.com/eventarc/docs
    """

    resource_type = "eventarc"
    # Cloudfunctions gen 2 is also supported (see https://cloud.google.com/functions/docs/calling/eventarc)
    # However, the implementation is complicated because it is difficult to route the responses to the correct trigger
    # Partial implementation can be found here: https://github.com/samdevo/goblet/blob/eventarc-changes/goblet/resources/eventarc.py
    valid_backends = ["cloudrun"]
    can_sync = True
    required_apis = ["eventarc"]
    permissions = [*gcp_generic_resource_permissions("eventarc", "triggers")]

    def __init__(self, name, backend, versioned_clients=None, resources=None):
        super(EventArc, self).__init__(
            name,
            versioned_clients=versioned_clients,
            resources=resources,
            backend=backend,
        )
        self.resources = resources or []

    def register(self, name, func, kwargs):
        event_filters = kwargs.get("event_filters")
        region = kwargs.get("kwargs", {}).get("region", get_default_location())
        event_data_content_type = kwargs.get("kwargs", {}).get(
            "event_data_content_type", "application/json"
        )
        if kwargs.get("topic"):
            event_filters = [
                {
                    "attribute": "type",
                    "value": "google.cloud.pubsub.topic.v1.messagePublished",
                }
            ]
        self.resources.append(
            {
                "trigger_name": f"{self.name}-{name}".replace("_", "-"),
                "event_filters": event_filters,
                "topic": kwargs["topic"],
                "region": region,
                "name": name,
                "func": func,
                "event_data_content_type": event_data_content_type,
            }
        )

    def __call__(self, request):
        full_path = request.path
        trigger_name = full_path.split("/")[-1]
        trigger = None
        for t in self.resources:
            if t["trigger_name"] in trigger_name:
                trigger = t
                break
        if not trigger:
            raise ValueError("No trigger found")
        response = trigger["func"](request)
        if not response:
            response = Response("success")
        return response

    def __add__(self, other):
        self.resources.extend(other.resources)
        return self

    def _deploy(self, sourceUrl=None, entrypoint=None):
        if not self.resources:
            return
        if self.config.eventarc and self.config.eventarc.get("serviceAccount"):
            service_account = self.config.eventarc.get("serviceAccount")
        elif self.config.cloudrun and self.config.cloudrun.get("service-account"):
            service_account = self.config.cloudrun.get("service-account")
        else:
            raise ValueError(
                "Service account not found for cloudrun or eventarc. You can set `serviceAccount` field in config.json under `eventarc`"
            )

        self.service_accounts = [service_account]

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
                    "cloudRun": {
                        "service": self.name,
                        "region": get_default_location(),
                        "path": f"/x-goblet-eventarc-triggers/{trigger['trigger_name']}",
                    }
                },
                "labels": self.config.labels,
                "eventDataContentType": trigger["event_data_content_type"],
                **topic,
            }
            create_eventarc_trigger(
                self.versioned_clients.eventarc,
                trigger["trigger_name"],
                trigger["region"],
                req_body,
            )

    def _sync(self, dryrun=False):
        """Only supports 1 region per sync"""
        triggers = self.versioned_clients.eventarc.execute(
            "list", parent_key="parent"
        ).get("triggers", [])
        filtered_triggers = list(
            filter(
                lambda trigger: f"/triggers/{self.name}-" in trigger["name"], triggers
            )
        )
        for filtered_trigger in filtered_triggers:
            filtered_name = filtered_trigger["name"].split("/")[-1]
            found = False
            for resource_trigger in self.resources:
                if resource_trigger["trigger_name"] == filtered_name:
                    found = True
                    break
            if not found:
                log.info(
                    f'Detected unused subscription in GCP {filtered_trigger["name"]}'
                )
                if not dryrun:
                    region = filtered_trigger["name"].split("/")[3]
                    destroy_eventarc_trigger(
                        self.versioned_clients.eventarc,
                        filtered_name,
                        region,
                    )

    def destroy(self):
        for trigger in self.resources:
            destroy_eventarc_trigger(
                self.versioned_clients.eventarc,
                trigger["trigger_name"],
                trigger["region"],
            )
