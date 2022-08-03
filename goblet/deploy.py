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
import math

from googleapiclient.errors import HttpError

from goblet.client import (
    VersionedClients,
    get_default_project,
    get_default_location,
    get_default_project_number
)
from goblet.common_cloud_actions import (
    create_cloudfunction,
    create_cloudbuild,
    destroy_cloudfunction,
    destroy_cloudfunction_artifacts,
    destroy_cloudrun,
    deploy_cloudrun
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
                self.zip("cloudfunction")
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
                log.info("zipping cloudrun......")
                self.zip("cloudrun")
                log.info("uploading cloudrun source zip to gs......")
                source = self._upload_zip(versioned_clients.run_uploader)["storageSource"]

                self.create_build(
                    versioned_clients.cloudbuild,
                    source,
                    self.name,
                    config
                )
                serviceRevision = RevisionSpec(config, versioned_clients, self.name)
                serviceRevision.deployRevision() 

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

    def create_build(self, client, source=None, name="goblet", config={}):
        """Creates http cloudbuild"""
        config = GConfig(config=config)
        user_configs = config.cloudrun or {}
        registry = user_configs.get("artifact_registry") or f"{get_default_location()}-docker.pkg.dev/{get_default_project()}/cloud-run-source-deploy/{name}"

        req_body = {
            "source": {"storageSource" : {"object": source["object"], "bucket": source["bucket"]}},
            "steps": [ {
            "name": "gcr.io/cloud-builders/docker",
            "args": ["build", "-t", registry, "."]
            }
            ],
            "images": [
                [registry]
            ]
        }


        create_cloudbuild(client, req_body)

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

    def _upload_zip(self, client) -> dict:
        """Uploads zipped cloudfunction using generateUploadUrl endpoint"""
        self.zipf.close()
        zip_size = os.stat(f".goblet/{self.name}.zip").st_size
        with open(f".goblet/{self.name}.zip", "rb") as f:
            resp = client.execute("generateUploadUrl", params={"body": {}})
            put_headers = {
                "content-type": "application/zip",
                "Content-Length": str(zip_size),
            }
            if client.version == "v1":
                put_headers["x-goog-content-length-range"] = "0,104857600"

            requests.put(
                resp["uploadUrl"],
                data=f,
                headers=put_headers,
            ).raise_for_status()

        log.info("function code uploaded")

        return resp

    def create_zip(self):
        """Creates initial goblet zipfile"""
        if not os.path.isdir(get_g_dir()):
            os.mkdir(get_g_dir())
        return zipfile.ZipFile(
            get_g_dir() + f"/{self.name}.zip", "w", zipfile.ZIP_DEFLATED
        )

    def zip(self, backend="cloudfunction"):
        """Zips requirements.txt, python files and any additional files based on config.customFiles"""
        if backend == "cloudfunction":
            config = GConfig()
            self.zip_file("requirements.txt")
            if config.main_file:
                self.zip_file(config.main_file, "main.py")
            include = config.customFiles or []
            include.append("*.py")
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                self.zip_directory(get_dir() + "/*", include=include)
        elif backend == "cloudrun":
            config = GConfig()
            self.zip_file("requirements.txt")
            if not os.path.exists(get_dir() + "/Dockerfile") and not os.path.exists(
                get_dir() + "/Procfile"
            ):
                log.info(
                    "No Dockerfile or Procfile found for cloudrun backend. Writing default Dockerfile"
                )
                write_dockerfile()
            self.zip_file("Dockerfile")
            if config.main_file:
                self.zip_file(config.main_file, "main.py")
            include = config.customFiles or []
            include.append("*.py")
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                self.zip_directory(get_dir() + "/*", include=include)
        else:
            raise ValueError(f"backend (given {backend}) must be cloudfunction or cloudrun")

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


class RevisionSpec:
    def __init__(
        self,
        config = {},
        versioned_clients = None,
        name = "goblet"
    ):
        self.versioned_clients = versioned_clients
        config = GConfig(config=config)
        self.cloudrun_configs = config.cloudrun or {}
        self.cloudrun_revision = config.cloudrun_revision or {}
        self.req_body = {}
        self.latestArtifact = ""
        self.name = name
    
    # calls latest build and checks for its artifact to avoid image:latest behavior with cloud run revisions
    def getArtifact(self):
        defaultProject = get_default_project()
        buildClient = self.versioned_clients.cloudbuild
        resp = buildClient.execute(
            "list",
            parent_key="projectId",
            parent_schema=defaultProject,
            params={}
        )
        latestBuildId = resp["builds"][0]["id"]
        resp = buildClient.execute(
            "get",
            parent_key="projectId",
            parent_schema=defaultProject,
            params={"id": latestBuildId}
        )
        self.latestArtifact = resp["results"]["images"][0]["name"] + "@" + resp["results"]["images"][0]["digest"]
        
    # splits traffic proportionaly from already deployed traffic 
    def modifyTraffic(self):
        client = self.versioned_clients.run
        region = get_default_location()
        trafficSpec = self.cloudrun_configs.get("traffic")
        trafficList = []

        # get initial service config
        resp = client.execute(
            "get",
            parent_key="name",
            parent_schema=f"projects/{get_default_project_number()}/locations/{region}/services/{self.name}",
            params={}
        )

        # proportion of total traffic specified
        trafficQuotient = (100-trafficSpec) / 100
        # using the max for additional modifications
        maxTrafficVal = 0
        maxTrafficLoc = 0
        maxTraffic = {}
        # keep track of the total traffic
        trafficSum = 0

        for traffics in resp["trafficStatuses"]:
            newPercent = math.ceil(traffics["percent"] * trafficQuotient)

            if traffics["type"] == "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST":

                newTraffic = {
                    "type": "TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION",
                    "revision": resp["latestReadyRevision"].rpartition('/')[-1],
                    "percent": newPercent
                }

            else:
                newTraffic = {
                    "type": "TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION",
                    "revision": traffics["revision"],
                    "percent": newPercent
                }
            
            trafficList.append(newTraffic)           
            if traffics["percent"] > maxTrafficVal:
                maxTrafficLoc = len(trafficList) - 1
                maxTraffic = newTraffic
            trafficSum += newPercent
        
        latestRevisionTraffic = {
            "type": "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST",
            "percent": trafficSpec
        }
        trafficList.append(latestRevisionTraffic) 

        if trafficSpec > maxTrafficVal:
            maxTrafficLoc = len(trafficList) - 1
            maxTraffic = latestRevisionTraffic
            trafficSum += trafficSpec

        if trafficSum > 100:
            sub_from_max = trafficSum - 100
            maxTraffic["percent"] -= sub_from_max
            trafficList[maxTrafficLoc] = maxTraffic

        self.req_body["traffic"] = trafficList

    def deployRevision(self):
        client = self.versioned_clients.run
        region = get_default_location()
        self.getArtifact()
        self.req_body = {
            "template": {
                "containers": [
                    {
                    "image": self.latestArtifact
                    }
                ],
                **self.cloudrun_revision
            }

        }

        #check for traffic config
        if self.cloudrun_configs.get("traffic"):
            # check all services for the name of the service
            resp = client.execute(
                "list",
                parent_key="parent",
                parent_schema=f"projects/98058317567/locations/{region}",
                params={}
            )

            for service in resp["services"]:
                if service["name"].rpartition('/')[-1] == self.name:               
                    self.modifyTraffic()

        deploy_cloudrun(client, self.req_body, self.name)            