from goblet.backends.backend import Backend
from goblet.client import VersionedClients, get_default_project, get_default_location
from goblet.common_cloud_actions import get_function_runtime, create_cloudfunction


class CloudFunctionV2(Backend):
    resource_type = "cloudfunction"
    supported_versions = ["v2beta", "v2alpha"]

    def __init__(self, app, config={}):
        self.client = VersionedClients(app.client_versions).cloudfunctions
        self.func_path = f"projects/{get_default_project()}/locations/{get_default_location()}/functions/{app.function_name}"
        super().__init__(app, self.client, self.func_path, config=config)

    def deploy(self, force=False):
        put_headers = {
            "content-type": "application/zip",
        }
        source = self._gcs_upload(self.client, put_headers, force=force)
        if self.app.is_http():
            client, params = self._get_upload_params(source)
            create_cloudfunction(client, params, config=self.config)

    def _get_upload_params(self, source):
        user_configs = self.config.cloudfunction or {}
        params = {
            "body": {
                "name": self.func_path,
                "environment": "GEN_2",
                "description": self.config.description or "created by goblet",
                "buildConfig": {
                    "runtime": get_function_runtime(self.client, self.config),
                    "entryPoint": "goblet_entrypoint",
                    "source": {
                        "storageSource": source["storageSource"]
                    }
                },
                **user_configs,
            }
        }
        return self.client, params
