from goblet.common_cloud_actions import (
    create_eventarc_trigger,
    destroy_eventarc_trigger,
    get_function_runtime,
    create_cloudfunctionv2,
)
from goblet.config import GConfig
from goblet.response import Response
import logging

from goblet.resources.handler import Handler
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
    can_sync = True

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
            if self.backend == "cloudrun":
                event_filters = [
                    {
                        "attribute": "type",
                        "value": "google.cloud.pubsub.topic.v1.messagePublished",
                    },
                ]
        if not event_filters:
            raise ValueError("Missing event_filters argument")

        # allow event_filters to optionally be specified as a dict (less verbose)
        if isinstance(event_filters, dict):
            event_filters = [
                {
                    "attribute": k,
                    "value": v,
                }
                for k, v in event_filters.items()
            ]
        assert isinstance(event_filters, list)
        if "type" not in (event["attribute"] for event in event_filters):
            raise ValueError("Key 'type' (required) not found in event_filters")
        event_type = None
        if self.backend == "cloudfunctionv2":
            # pop event_type from filters
            event_type = next(
                event
                for event in event_filters
                if event["attribute"] == "type"
            )
            event_filters.remove(event_type)

        self.resources.append(
            {
                "trigger_name": f"{self.name}-{name}".replace("_", "-"),
                "event_type": event_type["value"],
                "event_filters": event_filters,
                "topic": kwargs["topic"],
                "region": region,
                "name": name,
                "func": func,
            }
        )

    @staticmethod
    def _check_filters(data, filters):
        for f in filters:
            if f.get("operator"):
                # TODO
                continue
            log.info(data)
            log.info(f)
            if data[f["attribute"]] != data[f["value"]]:
                return False
        return True

    def __call__(self, request, context=None):
        trigger = None
        if self.backend == "cloudfunctionv2":
            for t in self.resources:
                if not self._check_filters(request, t["event_filters"]):
                    continue
                if t["event_type"] == context["event_type"]:
                    trigger = t
                    break
                # handle difference in naming for cloud storage triggers
                elif t["event_type"].startswith("google.cloud.storage.object.v1."):
                    if t["event_type"].split(".")[-1] == context["event_type"] + "d":
                        trigger = t
                        break
        else:
            full_path = request.path
            trigger_name = full_path.split("/")[-1]

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

    def _deploy(self, source=None, entrypoint=None, config={}):
        if not self.resources:
            return
        if self.backend == "cloudrun":
            self._deploy_eventarc_cloudrun(source, entrypoint, config)
        elif self.backend == "cloudfunctionv2":
            self._deploy_eventarc_cloudfunctionv2(source, entrypoint, config)

    def _deploy_eventarc_cloudfunctionv2(self, source=None, entrypoint=None, config={}):
        client = self.versioned_clients.cloudfunctions
        gconfig = GConfig(config=config)
        user_configs = gconfig.cloudfunction or {}
        service_account = None
        if gconfig.eventarc and gconfig.eventarc.get("serviceAccount"):
            service_account = gconfig.eventarc.get("serviceAccount")
        else:
            log.info(
                "Service account not found for cloudfunctions or eventarc. You can set `serviceAccount` "
                "field in config.json under `eventarc`"
            )
        for trigger in self.resources:
            # separate eventType from the rest of the event filters
            trigger_spec = {
                "eventType": trigger["event_type"],
                "eventFilters": trigger["event_filters"],
            }
            if service_account:
                trigger_spec["serviceAccountEmail"] = service_account
            params = {
                "body": {
                    "name": self.cloudfunction,
                    "environment": "GEN_2",
                    "description": gconfig.description or "created by goblet",
                    "buildConfig": {
                        "runtime": get_function_runtime(client, gconfig),
                        "entryPoint": entrypoint or "goblet_entrypoint",
                        "source": {"storageSource": source["storageSource"]},
                    },
                    "eventTrigger": trigger_spec,
                    **user_configs,
                },
                "functionId": self.cloudfunction.split("/")[-1],
            }
            create_cloudfunctionv2(client, params, config=config)

    def _deploy_eventarc_cloudrun(self, source=None, entrypoint=None, config={}):
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
                    "cloudRun": {
                        "service": self.name,
                        "region": get_default_location(),
                        "path": f"/x-goblet-eventarc-triggers/{trigger['trigger_name']}",
                    }
                },
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
