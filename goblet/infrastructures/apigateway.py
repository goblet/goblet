import logging
import os

from goblet.common_cloud_actions import deploy_apigateway, destroy_apigateway
from goblet.infrastructures.infrastructure import Infrastructure
from goblet.handlers.routes import OpenApiSpec
from goblet.utils import get_g_dir, get_dir
from goblet.permissions import gcp_generic_resource_permissions

log = logging.getLogger("goblet.deployer")
log.setLevel(logging.getLevelName(os.getenv("GOBLET_LOG_LEVEL", "INFO")))


class ApiGateway(Infrastructure):
    """Api Gateway that is deployed with an existing openapi spec"""

    resource_type = "apigateway"
    required_apis = ["apigateway"]
    permissions = [
        "apigateway.operations.get",
        *gcp_generic_resource_permissions("apigateway", "apiconfigs"),
        *gcp_generic_resource_permissions("apigateway", "apis"),
        *gcp_generic_resource_permissions("apigateway", "gateways"),
    ]

    def register(self, name, **kwargs):
        kwargs = kwargs["kwargs"]
        self.resources = {
            "name": name,
            "backend_url": kwargs["backend_url"],
            "openapi_dict": kwargs["openapi_dict"],
        }

    def _deploy(self):
        if not self.resources:
            return
        goblet_spec = OpenApiSpec(
            self.resources["name"],
            self.resources["backend_url"],
            existing_spec=self.resources["openapi_dict"],
        )
        goblet_spec.add_x_google_backend()

        # create .goblet if doesnt exist
        if not os.path.isdir(f"{get_dir()}/.goblet"):
            os.mkdir(f"{get_dir()}/.goblet")

        updated_filename = f"{get_g_dir()}/{self.resources['name']}_openapi_spec.yml"
        with open(updated_filename, "w") as f:
            goblet_spec.write(f)
        deploy_apigateway(
            self.resources["name"],
            self.config,
            self.versioned_clients,
            updated_filename,
        )

    def destroy(self):
        if not self.resources:
            return
        destroy_apigateway(self.resources["name"], self.versioned_clients)
