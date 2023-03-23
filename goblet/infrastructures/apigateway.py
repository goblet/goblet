import logging

from goblet.common_cloud_actions import deploy_apigateway, destroy_apigateway
from goblet.infrastructures.infrastructure import Infrastructure
from goblet.resources.routes import OpenApiSpec
from goblet.utils import get_g_dir

log = logging.getLogger("goblet.deployer")
log.setLevel(logging.INFO)


class ApiGateway(Infrastructure):
    """Api Gateway that is deployed with an existing openapi spec"""

    resource_type = "apigateway"

    def register(self, name, **kwargs):
        kwargs = kwargs["kwargs"]
        self.resource = {
            "name": name,
            "backend_url": kwargs["backend_url"],
            "openapi_dict": kwargs["openapi_dict"],
        }

    def deploy(self, config={}):
        if not self.resource:
            return
        self.config.update_g_config(values=config)
        goblet_spec = OpenApiSpec(
            self.resource["name"],
            self.resource["backend_url"],
            existing_spec=self.resource["openapi_dict"],
        )
        goblet_spec.add_x_google_backend()
        updated_filename = f"{get_g_dir()}/{self.name}_openapi_spec.yml"
        with open(updated_filename, "w") as f:
            goblet_spec.write(f)
        deploy_apigateway(
            self.resource["name"], self.config, self.client, updated_filename
        )

    def destroy(self):
        destroy_apigateway(self.resource["name"], self.client)
