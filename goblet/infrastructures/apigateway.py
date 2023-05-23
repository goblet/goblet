import logging
import os

from goblet.common_cloud_actions import deploy_apigateway, destroy_apigateway
from goblet.infrastructures.infrastructure import Infrastructure
from goblet.handlers.routes import OpenApiSpec
from goblet.utils import get_g_dir, get_dir

log = logging.getLogger("goblet.deployer")
log.setLevel(logging.getLevelName(os.getenv("GOBLET_LOG_LEVEL", "INFO")))


class ApiGateway(Infrastructure):
    """Api Gateway that is deployed with an existing openapi spec"""

    resource_type = "apigateway"
    required_apis = ["apigateway"]

    def register(self, name, **kwargs):
        kwargs = kwargs["kwargs"]
        self.resource = {
            "name": name,
            "backend_url": kwargs["backend_url"],
            "openapi_dict": kwargs["openapi_dict"],
        }

    def deploy(self):
        if not self.resource:
            return
        goblet_spec = OpenApiSpec(
            self.resource["name"],
            self.resource["backend_url"],
            existing_spec=self.resource["openapi_dict"],
        )
        goblet_spec.add_x_google_backend()

        # create .goblet if doesnt exist
        if not os.path.isdir(f"{get_dir()}/.goblet"):
            os.mkdir(f"{get_dir()}/.goblet")

        updated_filename = f"{get_g_dir()}/{self.resource['name']}_openapi_spec.yml"
        with open(updated_filename, "w") as f:
            goblet_spec.write(f)
        deploy_apigateway(
            self.resource["name"], self.config, self.versioned_clients, updated_filename
        )

    def destroy(self):
        if not self.resource:
            return
        destroy_apigateway(self.resource["name"], self.versioned_clients)
