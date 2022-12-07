import logging
import math

from goblet.client import (
    get_default_location,
    get_default_project_number,
)
from goblet.common_cloud_actions import deploy_cloudrun, getCloudbuildArtifact
from goblet.config import GConfig

log = logging.getLogger("goblet.deployer")
log.setLevel(logging.INFO)


class RevisionSpec:
    def __init__(self, config={}, versioned_clients=None, name="goblet"):
        self.versioned_clients = versioned_clients
        if not isinstance(config, GConfig):
            config = GConfig(config=config)
        self.config = config
        self.cloudrun_configs = config.cloudrun or {}
        self.cloudrun_revision = config.cloudrun_revision or {}
        self.cloudrun_container = config.cloudrun_container or {}
        self.cloudrun_container["command"] = self.cloudrun_container.get("command") or [
            "functions-framework",
            "--target=goblet_entrypoint",
        ]
        self.req_body = {}
        self.latestArtifact = ""
        self.name = name

    def getServiceConfig(self):
        client = self.versioned_clients.run
        serviceConfig = client.execute(
            "get",
            parent_key="name",
            parent_schema=f"projects/{get_default_project_number()}/locations/{get_default_location()}/services/{self.name}",
            params={},
        )
        return serviceConfig

    # splits traffic proportionaly from already deployed traffic
    def modifyTraffic(self, serviceConfig={}):
        trafficSpec = self.cloudrun_configs.get("traffic")
        trafficList = []

        # proportion of total traffic specified
        trafficQuotient = (100 - trafficSpec) / 100
        # using the max for additional modifications
        maxTrafficVal = 0
        maxTrafficLoc = 0
        maxTraffic = {}
        # keep track of the total traffic
        trafficSum = 0

        for traffics in serviceConfig["trafficStatuses"]:
            newPercent = math.ceil(traffics["percent"] * trafficQuotient)

            if traffics["type"] == "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST":

                newTraffic = {
                    "type": "TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION",
                    "revision": serviceConfig["latestReadyRevision"].rpartition("/")[
                        -1
                    ],
                    "percent": newPercent,
                }

            else:
                newTraffic = {
                    "type": "TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION",
                    "revision": traffics["revision"],
                    "percent": newPercent,
                }

            trafficList.append(newTraffic)
            if traffics["percent"] > maxTrafficVal:
                maxTrafficLoc = len(trafficList) - 1
                maxTraffic = newTraffic
            trafficSum += newPercent

        latestRevisionTraffic = {
            "type": "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST",
            "percent": trafficSpec,
        }
        trafficList.append(latestRevisionTraffic)

        if trafficSpec > maxTrafficVal:
            maxTrafficLoc = len(trafficList) - 1
            maxTraffic = latestRevisionTraffic
            trafficSum += trafficSpec

        if trafficSum > 100:
            sub_from_max = trafficSum - 100
            maxTraffic["percent"] -= sub_from_max
            trafficList[maxTrafficLoc] = maxTraffic

        self.req_body["traffic"] = trafficList

    def deployRevision(self):
        client = self.versioned_clients.run
        region = get_default_location()
        project = get_default_project_number()
        self.latestArtifact = getCloudbuildArtifact(
            self.versioned_clients.cloudbuild, self.name, config=self.config
        )
        self.req_body = {
            "template": {
                **self.cloudrun_revision,
            },
            "labels": {**self.config.labels},
            **self.cloudrun_configs,
        }
        self.req_body["template"]["containers"] = [{**self.cloudrun_container}]
        self.req_body["template"]["containers"][0]["image"] = self.latestArtifact

        # check for traffic config
        if self.cloudrun_configs.get("traffic"):
            # check all services for the name of the service
            resp = client.execute(
                "list",
                parent_key="parent",
                parent_schema=f"projects/{project}/locations/{region}",
                params={},
            )

            for service in resp["services"]:
                if service["name"].rpartition("/")[-1] == self.name:
                    serviceConfig = self.getServiceConfig()
                    self.modifyTraffic(serviceConfig)

        deploy_cloudrun(client, self.req_body, self.name)
