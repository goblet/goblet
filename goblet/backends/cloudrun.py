import os
import subprocess
import sys

from goblet.backends.backend import Backend
from goblet.client import VersionedClients, get_default_project, get_default_location
from goblet.config import GConfig
from goblet.utils import get_dir
from goblet.write_files import write_dockerfile


class CloudRun(Backend):
    resource_type = "cloudrun"
    supported_versions = ["v1"]  # do we support v2?

    def __init__(self, app, config={}):
        self.client = VersionedClients(app.client_versions).run
        self.func_path = f"projects/{get_default_project()}/locations/{get_default_location()}/services/{app.function_name}"
        self.zip_config = None  # TODO
        super().__init__(app, self.client, self.func_path, config=config)

    def deploy(self, force=False, config=None):
        if config:
            config = GConfig(config=config)
        else:
            config = self.config
        # put_headers = {
        #     "content-type": "application/zip",
        # }
        # source = self._gcs_upload(self.client, put_headers, force=force)
        # TODO start cloud build here (source already deployed, replace code below)
        cloudrun_configs = config.cloudrun or {}
        if not cloudrun_configs.get("no-allow-unauthenticated") or cloudrun_configs.get(
            "allow-unauthenticated"
        ):
            cloudrun_configs["no-allow-unauthenticated"] = None
        cloudrun_options = []
        for k, v in cloudrun_configs.items():
            # Handle multiple entries with the same key ex. update-env-vars
            if v and isinstance(v, list):
                for v_item in v:
                    cloudrun_options.append(f"--{k}")
                    cloudrun_options.append(v_item)
            else:
                cloudrun_options.append(f"--{k}")
                if v:
                    cloudrun_options.append(v)

        # Set default port to 8080
        if not cloudrun_configs.get("port"):
            cloudrun_options.append("--port")
            cloudrun_options.append("8080")

        # Set default command
        if not cloudrun_configs.get("command"):
            cloudrun_options.append("--command")
            cloudrun_options.append("functions-framework,--target=goblet_entrypoint")

        base_command = [
            "gcloud",
            "run",
            "deploy",
            self.name,
            "--project",
            get_default_project(),
            "--region",
            get_default_location(),
            "--source",
            get_dir(),
        ]
        if self.app.client_versions.get("gcloud"):
            base_command.insert(1, self.app.client_versions.get("gcloud"))
        base_command.extend(cloudrun_options)
        try:
            if not os.path.exists(get_dir() + "/Dockerfile") and not os.path.exists(
                get_dir() + "/Procfile"
            ):
                self.log.info(
                    "No Dockerfile or Procfile found for cloudrun backend. Writing default Dockerfile"
                )
                write_dockerfile()
            subprocess.check_output(base_command, env=os.environ)
        except subprocess.CalledProcessError:
            self.log.error(
                "Error during cloudrun deployment while running the following command"
            )
            self.log.error((" ").join(base_command))
            sys.exit(1)

        # Set IAM Bindings
        if config.bindings:
            self.log.info(f"adding IAM bindings for cloudrun {self.name}")
            policy_bindings = {"policy": {"bindings": config.bindings}}
            self.client.execute(
                "setIamPolicy",
                parent_key="resource",
                parent_schema=self.func_path,
                params={"body": policy_bindings},
            )
