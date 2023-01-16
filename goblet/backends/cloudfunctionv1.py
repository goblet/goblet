from requests import request


from goblet.backends.backend import Backend
from goblet.client import VersionedClients, get_default_location, get_default_project
from goblet.common_cloud_actions import (
    get_function_runtime,
    create_cloudfunctionv1,
    destroy_cloudfunction_artifacts,
    destroy_cloudfunction,
)


class CloudFunctionV1(Backend):
    resource_type = "cloudfunction"
    supported_versions = ["v1"]
    required_files = ["requirements.txt", "main.py"]
    config_key = "cloudfunction"
    monitoring_type = "cloud_function"
    monitoring_label_key = "function_name"

    def __init__(self, app, config={}):
        self.client = VersionedClients(app.client_versions).cloudfunctions
        self.func_path = f"projects/{get_default_project()}/locations/{get_default_location()}/functions/{app.function_name}"
        super().__init__(app, self.client, self.func_path, config=config)

    def deploy(self, force=False, config=None):
        if config:
            self.config.update_g_config(values=config)
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
                "labels": {**self.config.labels},
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

    def update_config(self, infra_configs=[], write_config=False, stage=None):
        config_updates = {self.config_key: {}}
        for infra_config in infra_configs:
            resource_type = infra_config["resource_type"]
            if resource_type == "vpcconnector":
                config_updates[self.config_key] = {
                    **config_updates.get(self.config_key, {}),
                    "vpcConnector": infra_config["values"]["name"],
                    "vpcConnectorEgressSettings": infra_config["values"]["egress"],
                }

            elif resource_type in ("redis"):
                config_updates[self.config_key]["environmentVariables"] = {
                    **config_updates[self.config_key].get("environmentVariables", {}),
                    **infra_config.get("values"),
                }

        self.config.update_g_config(
            values=config_updates, write_config=write_config, stage=stage
        )

    @property
    def http_endpoint(self):
        return f"https://{get_default_location()}-{get_default_project()}.cloudfunctions.net/{self.name}"

    # TODO:
    def set_iam_policy(self, service_account_id):
        client = self.client
        resource_name = self.func_path
        policy = {
            "policy": {
                "bindings": {
                    "role": "roles/cloudfunctions.invoker",
                    "members": [f"serviceAccount:{service_account_id}"],
                }
            }
        }
        client.execute(
            "setIamPolicy",
            params={"body": policy},
            parent_key="resource",
            parent_schema=resource_name,
        )

    def get_environment_vars(self):
        return self.config.config.get("cloudfunction", {}).get(
            "environmentVariables", {}
        )
