from requests import request


from goblet.backends.backend import Backend
from goblet.client import VersionedClients, get_default_project, get_default_location
from goblet.common_cloud_actions import (
    get_function_runtime,
    create_cloudfunctionv2,
    destroy_cloudfunction,
    destroy_cloudfunction_artifacts,
    get_cloudfunction_url,
)


class CloudFunctionV2(Backend):
    """Class for cloudfunctions second generation"""

    resource_type = "cloudfunctionv2"
    supported_versions = ["v2alpha", "v2beta", "v2"]
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
        build_configs = user_configs.get("buildConfig", {})
        if build_configs:
            del user_configs["buildConfig"]
        params = {
            "body": {
                "name": self.func_path,
                "environment": "GEN_2",
                "description": self.config.description or "created by goblet",
                "buildConfig": {
                    "runtime": get_function_runtime(self.client, config),
                    "entryPoint": "goblet_entrypoint",
                    "source": {"storageSource": source["storageSource"]},
                    **build_configs,
                },
                "labels": {**self.config.labels},
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

    def update_config(self, infra_configs=[], write_config=False, stage=None):
        config_updates = {self.config_key: {}}
        for infra_config in infra_configs:
            resource_type = infra_config["resource_type"]
            if resource_type == "vpcconnector":
                config_updates[self.config_key]["serviceConfig"] = {
                    **config_updates[self.config_key].get("serviceConfig", {}),
                    "vpcConnector": infra_config["values"]["name"],
                    "vpcConnectorEgressSettings": infra_config["values"]["egress"],
                }
            elif resource_type in ("redis"):
                config_updates[self.config_key]["serviceConfig"] = {
                    **config_updates[self.config_key].get("serviceConfig", {}),
                    "environmentVariables": {
                        **config_updates[self.config_key]
                        .get("serviceConfig", {})
                        .get("environmentVariables", {}),
                        **infra_config.get("values"),
                    },
                }
        self.config.update_g_config(
            values=config_updates, write_config=write_config, stage=stage
        )

    @property
    def http_endpoint(self):
        return get_cloudfunction_url(self.client, self.name)

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
        return (
            self.config.config.get("cloudfunction", {})
            .get("serviceConfig", {})
            .get("environmentVariables", {})
        )
