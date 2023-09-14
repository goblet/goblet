import os
import re
import base64
from urllib.parse import quote_plus

import google_auth_httplib2
from googleapiclient.errors import HttpError

from goblet.backends.backend import Backend
from goblet.client import VersionedClients
from goblet_gcp_client.client import (
    get_default_project,
    get_default_location,
    Client,
    get_credentials,
)
from goblet.common_cloud_actions import (
    create_cloudbuild,
    destroy_cloudrun,
    destroy_cloudfunction_artifacts,
    get_cloudrun_url,
    getDefaultRegistry,
    getDefaultRegistryName,
)
from goblet.revision import RevisionSpec
from goblet.utils import get_dir
from goblet.write_files import write_dockerfile
from goblet.errors import GobletValidationError
from goblet.permissions import gcp_generic_resource_permissions, add_binding


class CloudRun(Backend):
    resource_type = "cloudrun"
    supported_versions = ["v2"]
    monitoring_type = "cloud_run_revision"
    monitoring_label_key = "service_name"
    required_apis = ["run", "cloudbuild", "cloudfunctions", "cloudresourcemanager"]
    permissions = [
        *gcp_generic_resource_permissions("run", "services"),
        "run.services.getIamPolicy",
        "run.services.setIamPolicy",
        "run.revisions.get",
        "run.revisions.list",
        "run.operations.get",
        "cloudbuild.builds.create",
        "cloudbuild.builds.get",
        "cloudbuild.builds.list",
        "cloudresourcemanager.projects.get",
        "iam.serviceaccounts.actAs",
        "cloudfunctions.functions.sourceCodeSet",
        "artifactregistry.repositories.create",
        "artifactregistry.repositories.get",
    ]

    def __init__(self, app):
        self.client = VersionedClients().run
        self.run_name = f"projects/{get_default_project()}/locations/{get_default_location()}/services/{app.function_name}"
        super().__init__(app, self.client, self.run_name)

    def validation_config(self):
        name_pattern = r"^[a-z]([-a-z0-9]*[a-z0-9])?"
        pattern = re.compile(name_pattern)
        if not re.fullmatch(pattern, self.name):
            raise GobletValidationError(
                f"Invalid Cloudrun name {self.name}. Needs to follow regex of pattern {name_pattern}"
            )

    def deploy(self, force=False):
        versioned_clients = VersionedClients()
        put_headers = {
            "content-type": "application/zip",
        }

        if not os.path.exists(
            get_dir() + f"/{self.config.dockerfile or 'Dockerfile'}"
        ) and not os.path.exists(get_dir() + "/Procfile"):
            self.log.info(
                "No Dockerfile or Procfile found for cloudrun backend. Writing default Dockerfile"
            )
            write_dockerfile()

        try:
            artifact_tag = self.config.deploy.get("artifact_tag")
        except AttributeError:
            artifact_tag = None

        if artifact_tag:
            source, changes = None, False
            self.log.info(
                f"skipping zip/upload/build... cloudbuild.artifact {artifact_tag} found"
            )
        else:
            self._zip_file(self.config.dockerfile or "Dockerfile", "Dockerfile")
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
            serviceRevision = RevisionSpec(self.config, versioned_clients, self.name)
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
        build_configs = self.config.cloudbuild.copy() if self.config.cloudbuild else {}

        try:
            registry = self.config.deploy.get(
                "artifact_registry"
            ) or getDefaultRegistry(name)
        except AttributeError:
            registry = getDefaultRegistry(name)

        # check if default registry exists
        if registry == getDefaultRegistry(name):
            registry_client = VersionedClients().artifactregistry_repositories
            try:
                registry_client.execute(
                    "get", parent_key="name", parent_schema=getDefaultRegistryName()
                )
            except HttpError as e:
                # Registry doesn't exist
                if e.resp.status == 404:
                    # create registry
                    self.log.info(
                        f"Default registry doesn't exist. Creating registry {getDefaultRegistryName()}"
                    )
                    resp = registry_client.execute(
                        "create",
                        params={
                            "body": {
                                "name": getDefaultRegistryName(),
                                "format": "DOCKER",
                                "mode": "STANDARD_REPOSITORY",
                            },
                            "repositoryId": "cloud-run-source-deploy",
                        },
                    )
                registry_client.wait_for_operation(resp["name"])

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
                    "args": [
                        "build",
                        "--network=cloudbuild",
                        "-t",
                        registry,
                        "--cache-from",
                        registry,
                        ".",
                    ],
                }
            ],
            "images": [registry],
            **build_configs,
        }

        req_body["tags"] = build_configs.get("tags", []) + [f"goblet-build-{self.name}"]

        create_cloudbuild(client, req_body)

    def skip_deployment(self):
        return self.skip_run_deployment

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
        # Forces the deployment of cloud run
        if self.config.force_deploy_cloudrun:
            return False
        return skip

    def _checksum(self):
        versioned_clients = VersionedClients()
        resp = versioned_clients.cloudbuild.execute(
            "list",
            parent_key="projectId",
            parent_schema=get_default_project(),
            params={"filter": f"tags=goblet-build-{self.name}"},
        )
        if not resp:
            return 0
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
        # Append if job_container is set
        env.extend(self.config.config.get("job_container", {}).get("env", []))

        versioned_clients = VersionedClients()
        for env_item in env:
            # get secret
            if env_item.get("valueSource"):
                try:
                    secret_name = env_item["valueSource"]["secretKeyRef"]["secret"]
                    version = env_item["valueSource"]["secretKeyRef"].get(
                        "version", "latest"
                    )

                    resp = versioned_clients.secretmanager.execute(
                        "access",
                        parent_key="name",
                        parent_schema="projects/{project_id}/secrets/"
                        + secret_name
                        + "/versions/"
                        + version,
                    )

                    env_dict[env_item["name"]] = base64.b64decode(
                        resp["payload"]["data"]
                    ).decode()
                except Exception as e:
                    self.log.info(
                        f"Unable to get secret {env_item['name']} and set environment variable with error {str(e)}. Skipping..."
                    )
            else:
                env_dict[env_item["name"]] = env_item["value"]
        return env_dict

    def zip_required_files(self):
        """Zip required files for cloudrun. Requirements.txt is not required."""
        self._zip_config()
        if self.config.requirements_file:
            self._zip_file(self.config.requirements_file, "requirements.txt")
        if self.config.main_file:
            self._zip_file(self.config.main_file, "main.py")

    def add_invoker_binding(self, principles):
        add_binding(self.client, self.run_name, "roles/run.invoker", principles)
