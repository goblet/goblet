from googleapiclient.errors import HttpError
from goblet.config import GConfig
from goblet.infrastructures.infrastructure import Infrastructure

import logging

log = logging.getLogger("goblet.deployer")
log.setLevel(logging.INFO)


class VPCConnector(Infrastructure):

    resource_type = "vpcconnector"

    def register_connector(self, name, kwargs):
        self.resources = {"name": name}

    def deploy(self, config={}):
        if not self.resources:
            return
        config = GConfig(config=config)
        vpcconnector_config = config.vpcconnector or {}

        # either min/max throughput or instances needs to be set
        req_body = {
            "network": vpcconnector_config.get("network", "default"),
            "ipCidrRange": vpcconnector_config.get("ipCidrRange"),
            "minInstances": vpcconnector_config.get("minInstances", 2),  # DEFAULT
            "maxInstances": vpcconnector_config.get(
                "maxInstances", vpcconnector_config.get("minInstances", 2) + 1
            ),
            **vpcconnector_config,
        }

        try:
            resp = self.client.vpcconnector.execute(
                "create",
                params={"connectorId": self.resources["name"], "body": req_body},
            )
            self.client.vpcconnector.wait_for_operation(resp["name"])
        except HttpError as e:
            if e.resp.status == 409:
                log.info(
                    f"vpc connector {self.resources['name']} already exists, updating not supported"
                )
                pass
            else:
                raise e

    def get(self):
        if not self.resources:
            return
        resp = self.client.vpcconnector.execute(
            "get",
            parent_key="name",
            parent_schema="projects/{project_id}/locations/{location_id}/connectors/"
            + self.resources["name"],
        )
        return resp

    def destroy(self):
        if not self.resources:
            return
        try:
            resp = self.client.vpcconnector.execute(
                "delete",
                parent_key="name",
                parent_schema="projects/{project_id}/locations/{location_id}/connectors/"
                + self.resources["name"],
            )
            self.client.vpcconnector.wait_for_operation(resp["name"])
            log.info("destroying vpc connector")
        except HttpError as e:
            if e.resp.status == 404:
                log.info(f"vpc connector {self.resources['name']} already deleted")
            else:
                raise e

    def get_config(self):
        if not self.resources:
            return
        vpc_connector = self.get()

        return {
            "resource_type": self.resource_type,
            "values": {
                "name": vpc_connector["name"],
                "egress": "PRIVATE_RANGES_ONLY",
            },
        }
