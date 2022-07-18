from pathlib import Path
import zipfile
import os
import sys
import requests
import logging
import hashlib
from requests import request
import base64
import warnings
import subprocess

from googleapiclient.errors import HttpError

from goblet.client import (
    VersionedClients,
    get_default_project,
    get_default_location,
)
from goblet.common_cloud_actions import (
    create_cloudfunction,
    destroy_cloudfunction,
    destroy_cloudfunction_artifacts,
    destroy_cloudrun,
)
from goblet.utils import get_dir, get_g_dir, checksum, get_python_runtime
from goblet.write_files import write_dockerfile
from goblet.config import GConfig

log = logging.getLogger("goblet.deployer")
log.setLevel(logging.INFO)


class Deployer:
    """Deploys/Destroys goblet app and main cloudfunction. The main methods are deploy and destroy which both take in a Goblet instance"""

    def __init__(self, config={}):
        self.config = config
        if not config:
            self.config = {"name": "goblet"}
        self.name = self.config["name"]
        self.zipf = self.create_zip()
        self.func_name = f"projects/{get_default_project()}/locations/{get_default_location()}/functions/{self.name}"
        self.run_name = f"projects/{get_default_project()}/locations/{get_default_location()}/services/{self.name}"

    def package(self):
        self.zip()

    def deploy(
        self, goblet, skip_function=False, only_function=False, config={}, force=False
    ):
        """Deploys http cloudfunction and then calls goblet.deploy() to deploy any handler's required infrastructure"""
        source_url = None
        versioned_clients = VersionedClients(goblet.client_versions)
        if not skip_function:
            if goblet.backend == "cloudfunction":
                log.info("zipping function......")
                self.zip()
                if (
                    not force
                    and self.get_function(versioned_clients.cloudfunctions)
                    and not self._cloudfunction_delta(
                        versioned_clients.cloudfunctions, f".goblet/{self.name}.zip"
                    )
                ):
                    log.info("No changes detected......")
                else:
                    log.info("uploading function zip to gs......")
                    source_url = self._upload_zip(versioned_clients.cloudfunctions)
                    if goblet.is_http():
                        self.create_function(
                            versioned_clients.cloudfunctions,
                            source_url,
                            "goblet_entrypoint",
                            config,
                        )
            if goblet.backend == "cloudrun":
                self.create_cloudrun(versioned_clients, config)
        if not only_function:
            goblet.deploy(source_url, config=config)

        return goblet

    def sync(self, goblet, dryrun=False):
        """Call's handler's sync function to determine if gcp resources should be deleted based on the current configuration"""
        goblet.sync(dryrun=dryrun)
        return goblet

    def destroy(self, goblet, all=None):
        """Destroys http cloudfunction and then calls goblet.destroy() to remove handler's infrastructure"""
        goblet.destroy()
        versioned_clients = VersionedClients(goblet.client_versions)
        if goblet.backend == "cloudfunction":
            destroy_cloudfunction(versioned_clients.cloudfunctions, self.name)
        if goblet.backend == "cloudrun":
            destroy_cloudrun(versioned_clients.run, self.name)
        if all:
            destroy_cloudfunction_artifacts(self.name)

        return goblet

    def get_function(self, client):
        """Returns cloudfunction currently deployed or None"""
        try:
            return client.execute(
                "get", parent_key="name", parent_schema=self.func_name
            )
        except HttpError as e:
            if e.resp.status != 404:
                raise

    def create_function(self, client, url, entrypoint, config={}):
        """Creates http cloudfunction"""
        config = GConfig(config=config)
        user_configs = config.cloudfunction or {}
        req_body = {
            "name": self.func_name,
            "description": config.description or "created by goblet",
            "entryPoint": entrypoint,
            "sourceUploadUrl": url,
            "httpsTrigger": {},
            "runtime": get_python_runtime(),
            **user_configs,
        }
        create_cloudfunction(client, req_body, config=config.config)

    def create_cloudrun(self, client, config={}):
        """Creates http cloudfunction"""
        config = GConfig(config=config)
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
        if client.gcloud:
            base_command.insert(1, client.gcloud)
        base_command.extend(cloudrun_options)
        try:
            if not os.path.exists(get_dir() + "/Dockerfile") and not os.path.exists(
                get_dir() + "/Procfile"
            ):
                log.info(
                    "No Dockerfile or Procfile found for cloudrun backend. Writing default Dockerfile"
                )
                write_dockerfile()
            subprocess.check_output(base_command, env=os.environ)
        except subprocess.CalledProcessError:
            log.error(
                "Error during cloudrun deployment while running the following command"
            )
            log.error((" ").join(base_command))
            sys.exit(1)

        # Set IAM Bindings
        if config.bindings:
            log.info(f"adding IAM bindings for cloudrun {self.name}")
            policy_bindings = {"policy": {"bindings": config.bindings}}
            client.run.execute(
                "setIamPolicy",
                parent_key="resource",
                parent_schema=self.run_name,
                params={"body": policy_bindings},
            )

    def _cloudfunction_delta(self, client, filename):
        """Compares md5 hash between local zipfile and cloudfunction already deployed"""
        self.zipf.close()
        with open(filename, "rb") as fh:
            local_checksum = base64.b64encode(checksum(fh, hashlib.md5())).decode(
                "ascii"
            )

        source_info = client.execute(
            "generateDownloadUrl", parent_key="name", parent_schema=self.func_name
        )
        resp = request("HEAD", source_info["downloadUrl"])
        deployed_checksum = resp.headers["x-goog-hash"].split(",")[-1].split("=", 1)[-1]
        modified = deployed_checksum != local_checksum
        return modified

    def _upload_zip(self, client):
        """Uploads zipped cloudfunction using generateUploadUrl endpoint"""
        self.zipf.close()
        zip_size = os.stat(f".goblet/{self.name}.zip").st_size
        with open(f".goblet/{self.name}.zip", "rb") as f:
            resp = client.execute("generateUploadUrl", params={"body": {}})

            requests.put(
                resp["uploadUrl"],
                data=f,
                headers={
                    "content-type": "application/zip",
                    "Content-Length": str(zip_size),
                    "x-goog-content-length-range": "0,104857600",
                },
            )

        log.info("function code uploaded")

        return resp["uploadUrl"]

    def create_zip(self):
        """Creates initial goblet zipfile"""
        if not os.path.isdir(get_g_dir()):
            os.mkdir(get_g_dir())
        return zipfile.ZipFile(
            get_g_dir() + f"/{self.name}.zip", "w", zipfile.ZIP_DEFLATED
        )

    def zip(self):
        """Zips requirements.txt, python files and any additional files based on config.customFiles"""
        config = GConfig()
        self.zip_file("requirements.txt")
        if config.main_file:
            self.zip_file(config.main_file, "main.py")
        include = config.customFiles or []
        include.append("*.py")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.zip_directory(get_dir() + "/*", include=include)

    def zip_file(self, filename, arcname=None):
        self.zipf.write(filename, arcname)

    def zip_directory(
        self,
        dir,
        include=["*.py"],
        exclude=["build", "docs", "examples", "test", "tests", "venv"],
    ):
        exclusion_set = set(exclude)
        globbed_files = []
        for pattern in include:
            globbed_files.extend(Path("").rglob(pattern))
        for path in globbed_files:
            if not set(path.parts).intersection(exclusion_set):
                self.zipf.write(str(path))
