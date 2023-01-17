import os
from urllib.parse import quote_plus

import google_auth_httplib2

from goblet.backends.backend import Backend
from goblet.client import Client, get_credentials
from goblet.client import VersionedClients, get_default_project, get_default_location
from goblet.common_cloud_actions import (
    create_cloudbuild,
    destroy_cloudrun,
    destroy_cloudfunction_artifacts,
    get_cloudrun_url,
)
from goblet.revision import RevisionSpec
from goblet.utils import get_dir
from goblet.write_files import write_dockerfile


class CloudRun(Backend):
    resource_type = "cloudrun"
    supported_versions = ["v2"]
    monitoring_type = "cloud_run_revision"
    monitoring_label_key = "service_name"

    def __init__(self, app, config={}):
        self.client = VersionedClients(app.client_versions).run
        self.run_name = f"projects/{get_default_project()}/locations/{get_default_location()}/services/{app.function_name}"
        super().__init__(app, self.client, self.run_name, config=config)

    def deploy(self, force=False, config=None):
        versioned_clients = VersionedClients(self.app.client_versions)
        if config:
            self.config.update_g_config(values=config)
        config = self.config
        put_headers = {
            "content-type": "application/zip",
        }

        if not os.path.exists(get_dir() + "/Dockerfile") and not os.path.exists(
            get_dir() + "/Procfile"
        ):
            self.log.info(
                "No Dockerfile or Procfile found for cloudrun backend. Writing default Dockerfile"
            )
            write_dockerfile()
        self._zip_file("Dockerfile")

        source, changes = self._gcs_upload(
            self.client,
            put_headers,
            upload_client=versioned_clients.run_uploader,
            force=force,
        )

        if not changes:
            return None

        self.create_build(versioned_clients.cloudbuild, source, self.name)

        if not self.skip_run_deployment():
            serviceRevision = RevisionSpec(config, versioned_clients, self.name)
            serviceRevision.deployRevision()
        else:
            self.log.info("Skipping cloudrun deployment since it is not needed...")

        # Set IAM Bindings
        if not self.skip_run_deployment() and self.config.bindings:
            self.log.info(f"adding IAM bindings for cloudrun {self.name}")
            policy_bindings = {"policy": {"bindings": self.config.bindings}}
            self.client.execute(
                "setIamPolicy",
                parent_key="resource",
                parent_schema=self.run_name,
                params={"body": policy_bindings},
            )

        return source

    def destroy(self, all=False):
        destroy_cloudrun(self.client, self.name)
        if all:
            destroy_cloudfunction_artifacts(self.name)

    def create_build(self, client, source=None, name="goblet"):
        """Creates http cloudbuild"""
        build_configs = self.config.cloudbuild or {}
        registry = (
            build_configs.get("artifact_registry")
            or f"{get_default_location()}-docker.pkg.dev/{get_default_project()}/cloud-run-source-deploy/{name}"
        )
        build_configs.pop("artifact_registry", None)

        if build_configs.get("serviceAccount") and not build_configs.get("logsBucket"):
            build_options = build_configs.get("options", {})
            if not build_options.get("logging"):
                build_options["logging"] = "CLOUD_LOGGING_ONLY"
                build_configs["options"] = build_options
                self.log.info(
                    "service account given but no logging bucket so defaulting to cloud logging only"
                )

        req_body = {
            "source": {"storageSource": source["storageSource"]},
            "steps": [
                {
                    "name": "gcr.io/cloud-builders/docker",
                    "args": ["build", "--network=cloudbuild", "-t", registry, "."],
                }
            ],
            "images": [registry],
            **build_configs,
        }

        create_cloudbuild(client, req_body)

    def skip_run_deployment(self):
        """Skip cloudrun deployment if only jobs"""
        skip = True
        for name, handler in self.app.handlers.items():
            if handler.resources and name != "jobs" and name != "schedule":
                skip = False
            # scheduled jobs
            if handler.resources and name == "schedule":
                for schedule_name in handler.resources.keys():
                    if not schedule_name.startswith("schedule-job-"):
                        skip = False
        return skip

    def _checksum(self):
        versioned_clients = VersionedClients(self.app.client_versions)
        resp = versioned_clients.cloudbuild.execute(
            "list",
            parent_key="projectId",
            parent_schema=get_default_project(),
            params={},
        )
        latest_build_source = resp["builds"][0].get("source")
        if not latest_build_source:
            return 0
        bucket = latest_build_source["storageSource"]["bucket"]
        obj = latest_build_source["storageSource"]["object"]
        client = Client("cloudresourcemanager", "v1", calls="projects")
        http = client.http or google_auth_httplib2.AuthorizedHttp(get_credentials())
        resp = http.request(
            f"https://storage.googleapis.com/storage/v1/b/{bucket}/o/{quote_plus(obj)}?alt=media",
        )
        try:
            return resp[0]["x-goog-hash"].split(",")[-1].split("=", 1)[-1]
        except KeyError:
            return 0

    def update_config(self, infra_configs=[], write_config=False, stage=None):
        config_updates = {}
        for infra_config in infra_configs:
            resource_type = infra_config["resource_type"]
            if resource_type == "vpcconnector":
                config_updates["cloudrun_revision"] = {
                    **config_updates.get("cloudrun_revision", {}),
                    "vpcAccess": {
                        "connector": infra_config["values"]["name"],
                        "egress": infra_config["values"]["egress"],
                    },
                }
            else:
                envs = [
                    {"name": name, "value": value}
                    for name, value in infra_config["values"].items()
                ]
                env = config_updates.get("cloudrun_container", {}).get("env", [])
                env.extend(envs)

                config_updates["cloudrun_container"] = {
                    **config_updates.get("cloudrun_container", {}),
                    "env": env,
                }
        self.config.update_g_config(
            values=config_updates,
            write_config=write_config,
            stage=stage,
        )

    @property
    def http_endpoint(self):
        return get_cloudrun_url(self.client, self.name)

    def set_iam_policy(self, service_account_id):
        client = self.client
        policy = {
            "policy": {
                "bindings": {
                    "role": "roles/run.invoker",
                    "members": [f"serviceAccount:{service_account_id}"],
                }
            }
        }
        client.execute(
            "setIamPolicy",
            params={"body": policy},
            parent_key="resource",
            parent_schema=self.run_name,
        )

    def get_environment_vars(self):
        env_dict = {}
        env = self.config.config.get("cloudrun_container", {}).get("env", [])
        for env_item in env:
            env_dict[env_item["name"]] = env_item["value"]
        return env_dict
