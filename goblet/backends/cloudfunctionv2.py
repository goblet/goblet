from requests import request


from goblet.backends.backend import Backend
from goblet.client import VersionedClients, get_default_project, get_default_location
from goblet.common_cloud_actions import (
    get_function_runtime,
    create_cloudfunctionv2,
    destroy_cloudfunction,
    destroy_cloudfunction_artifacts,
)
from goblet.config import GConfig


class CloudFunctionV2(Backend):
    """Class for cloudfunctions second generation"""

    resource_type = "cloudfunctionv2"
    supported_versions = ["v2alpha", "v2beta", "v2"]

    def __init__(self, app, config={}):
        self.client = VersionedClients(app.client_versions).cloudfunctions
        self.func_path = f"projects/{get_default_project()}/locations/{get_default_location()}/functions/{app.function_name}"
        super().__init__(app, self.client, self.func_path, config=config)

    def deploy(self, force=False, config=None):
        if config:
            config = GConfig(config=config)
        else:
            config = self.config
        put_headers = {
            "content-type": "application/zip",
        }
        source, changes = self._gcs_upload(self.client, put_headers, force=force)
        if not changes:
            return None

        if self.app.is_http():
            client, params = self._get_upload_params(source, config=config)
            create_cloudfunctionv2(client, params, config=config)

        return source

    def destroy(self, all=False):
        destroy_cloudfunction(self.client, self.name)
        if all:
            destroy_cloudfunction_artifacts(self.name)

    def _get_upload_params(self, source, config=None):
        config = config or self.config
        user_configs = config.cloudfunction or {}
        params = {
            "body": {
                "name": self.func_path,
                "environment": "GEN_2",
                "description": self.config.description or "created by goblet",
                "buildConfig": {
                    "runtime": get_function_runtime(self.client, config),
                    "entryPoint": "goblet_entrypoint",
                    "source": {"storageSource": source["storageSource"]},
                },
                **user_configs,
            },
            "functionId": self.app.function_name,
        }
        return self.client, params

    def _checksum(self):
        source_info = self.client.execute(
            "generateDownloadUrl", parent_key="name", parent_schema=self.func_path
        )
        resp = request("HEAD", source_info["downloadUrl"])
        return resp.headers["x-goog-hash"].split(",")[-1].split("=", 1)[-1]
