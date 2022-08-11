from requests import request


from goblet.backends.backend import Backend
from goblet.client import VersionedClients, get_default_location, get_default_project
from goblet.common_cloud_actions import (
    get_function_runtime,
    create_cloudfunctionv1,
    destroy_cloudfunction_artifacts,
    destroy_cloudfunction,
)
from goblet.config import GConfig


class CloudFunctionV1(Backend):
    resource_type = "cloudfunction"
    supported_versions = ["v1"]

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
            "x-goog-content-length-range": "0,104857600",
        }
        source, changes = self._gcs_upload(self.client, put_headers, force=force)
        if not changes:
            return None

        if self.app.is_http():
            client, params = self._get_upload_params(source)
            create_cloudfunctionv1(client, params, config=config)

        return source

    def destroy(self, all=False):
        destroy_cloudfunction(self.client, self.name)
        if all:
            destroy_cloudfunction_artifacts(self.name)

    def _get_upload_params(self, source):
        user_configs = self.config.cloudfunction or {}
        params = {
            "body": {
                "name": self.func_path,
                "description": self.config.description or "created by goblet",
                "entryPoint": "goblet_entrypoint",
                "sourceUploadUrl": source["uploadUrl"],
                "httpsTrigger": {},
                "runtime": get_function_runtime(self.client, self.config),
                **user_configs,
            }
        }
        return self.client, params

    def _checksum(self):
        source_info = self.client.execute(
            "generateDownloadUrl", parent_key="name", parent_schema=self.func_path
        )
        resp = request("HEAD", source_info["downloadUrl"])
        return resp.headers["x-goog-hash"].split(",")[-1].split("=", 1)[-1]
