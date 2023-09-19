from googleapiclient.errors import HttpError
from goblet.infrastructures.infrastructure import Infrastructure
from goblet.permissions import gcp_generic_resource_permissions

import logging
import os

log = logging.getLogger("goblet.deployer")
log.setLevel(logging.getLevelName(os.getenv("GOBLET_LOG_LEVEL", "INFO")))


class VPCConnector(Infrastructure):
    resource_type = "vpcconnector"
    required_apis = ["vpcaccess"]
    permissions = [
        "vpcaccess.operations.get",
        gcp_generic_resource_permissions("vpcaccess", "connectors"),
    ]

    def register(self, name, kwargs):
        self.resources = {"name": name}
        vpcconnector_config = self.config.vpcconnector or {}

        if not vpcconnector_config.get("ipCidrRange"):
            raise ValueError("ipCidrRange not specified in config")

    def _deploy(self):
        if not self.resources:
            return
        vpcconnector_config = self.config.vpcconnector or {}

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
            resp = self.versioned_clients.vpcconnector.execute(
                "create",
                params={"connectorId": self.resources["name"], "body": req_body},
            )
            self.versioned_clients.vpcconnector.wait_for_operation(resp["name"])
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
        resp = self.versioned_clients.vpcconnector.execute(
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
            resp = self.versioned_clients.vpcconnector.execute(
                "delete",
                parent_key="name",
                parent_schema="projects/{project_id}/locations/{location_id}/connectors/"
                + self.resources["name"],
            )
            self.versioned_clients.vpcconnector.wait_for_operation(resp["name"])
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
