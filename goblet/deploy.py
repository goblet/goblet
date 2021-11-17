from pathlib import Path
import zipfile
import os
import requests
import logging
import hashlib
from requests import request
import base64
import json
from urllib.parse import quote_plus

from googleapiclient.errors import HttpError

from goblet.client import Client, get_default_project, get_default_location, get_credentials
from goblet.utils import get_dir, get_g_dir, checksum
from goblet.config import GConfig
import google_auth_httplib2

log = logging.getLogger('goblet.deployer')
log.setLevel(logging.INFO)


class Deployer:
    """Deploys/Destroys goblet app and main cloudfunction. The main methods are deploy and destroy which both take in a Goblet instance"""

    def __init__(self, config={}):
        self.config = config
        if not config:
            self.config = {
                "name": "goblet_test_app"
            }
        self.name = self.config["name"]
        self.zipf = self.create_zip()
        self.function_client = self._create_function_client()
        self.func_name = f"projects/{get_default_project()}/locations/{get_default_location()}/functions/{self.name}"

    def _create_function_client(self):
        return Client("cloudfunctions", 'v1', calls='projects.locations.functions', parent_schema='projects/{project_id}/locations/{location_id}')

    def package(self):
        self.zip()

    def deploy(self, goblet, skip_function=False, only_function=False, config=None, force=False):
        """Deploys http cloudfunction and then calls goblet.deploy() to deploy any handler's required infrastructure"""
        url = None
        if not skip_function:
            log.info("zipping function......")
            self.zip()
            if not force and self.get_function() and not self._cloudfunction_delta(f'.goblet/{self.name}.zip'):
                log.info("No changes detected......")
            else:
                log.info("uploading function zip to gs......")
                url = self._upload_zip()
                if goblet.is_http():
                    # TODO: temporary workaround around the goblet entrypoint.
                    self.create_function(url, "goblet_entrypoint", config)
                    # self.create_function(url, goblet.entrypoint, config)
        if not only_function and url:
            goblet.deploy(url)

        return goblet

    def destroy(self, goblet, all=None):
        """Destroys http cloudfunction and then calls goblet.destroy() to remove handler's infrastructure"""
        goblet.destroy()
        destroy_cloudfunction(self.name)
        if all:
            destroy_cloudfunction_artifacts(self.name)

        return goblet

    def get_function(self):
        """Returns cloudfunction currently deployed or None"""
        try:
            return self.function_client.execute('get', parent_key="name", parent_schema=self.func_name)
        except HttpError as e:
            if e.resp.status != 404:
                raise

    def create_function(self, url, entrypoint, config=None):
        """Creates http cloudfunction"""
        config = GConfig(config=config)
        user_configs = config.cloudfunction or {}
        req_body = {
            "name": self.func_name,
            "description": config.description or "created by goblet",
            "entryPoint": entrypoint,
            "sourceUploadUrl": url,
            "httpsTrigger": {},
            "runtime": "python37",
            **user_configs
        }
        create_cloudfunction(req_body, config=config.config)

    def _cloudfunction_delta(self, filename):
        """Compares md5 hash between local zipfile and cloudfunction already deployed"""
        self.zipf.close()
        with open(filename, 'rb') as fh:
            local_checksum = base64.b64encode(checksum(fh, hashlib.md5())).decode('ascii')

        source_info = self.function_client.execute('generateDownloadUrl', parent_key="name", parent_schema=self.func_name)
        resp = request('HEAD', source_info['downloadUrl'])
        deployed_checksum = resp.headers['x-goog-hash'].split(',')[-1].split('=', 1)[-1]
        modified = deployed_checksum != local_checksum
        return modified

    def _upload_zip(self):
        """Uploads zipped cloudfunction using generateUploadUrl endpoint"""
        self.zipf.close()
        zip_size = os.stat(f'.goblet/{self.name}.zip').st_size
        with open(f'.goblet/{self.name}.zip', 'rb') as f:
            resp = self.function_client.execute('generateUploadUrl', params={'body': {}})

            requests.put(
                resp["uploadUrl"],
                data=f,
                headers={
                    "content-type": "application/zip",
                    'Content-Length': str(zip_size),
                    "x-goog-content-length-range": "0,104857600"
                }
            )

        log.info("function code uploaded")

        return resp["uploadUrl"]

    def create_zip(self):
        """Creates initial goblet zipfile"""
        if not os.path.isdir(get_g_dir()):
            os.mkdir(get_g_dir())
        return zipfile.ZipFile(get_g_dir() + f'/{self.name}.zip', 'w', zipfile.ZIP_DEFLATED)

    def zip(self):
        """Zips requirements.txt, python files and any additional files based on config.customFiles"""
        config = GConfig()
        self.zip_file("requirements.txt")
        include = config.customFiles or []
        include.append('*.py')
        self.zip_directory(get_dir() + '/*', include=include)

    def zip_file(self, filename):
        self.zipf.write(filename)

    def zip_directory(self, dir, include=['*.py'], exclude=['build', 'docs', 'examples', 'test', 'venv']):
        exclusion_set = set(exclude)
        globbed_files = []
        for pattern in include:
            globbed_files.extend(Path('').rglob(pattern))
        for path in globbed_files:
            if not set(path.parts).intersection(exclusion_set):
                self.zipf.write(str(path))


def create_cloudfunction(req_body, config=None):
    """Creates a cloudfunction based on req_body"""
    function_name = req_body['name'].split('/')[-1]
    function_client = Client("cloudfunctions", 'v1', calls='projects.locations.functions', parent_schema='projects/{project_id}/locations/{location_id}')
    try:
        resp = function_client.execute('create', parent_key="location", params={'body': req_body})
        log.info(f"creating cloudfunction {function_name}")
    except HttpError as e:
        if e.resp.status == 409:
            log.info(f"updating cloudfunction {function_name}")
            resp = function_client.execute('patch', parent_key="name", parent_schema=req_body["name"], params={'body': req_body})
        else:
            raise e
    function_client.wait_for_operation(resp["name"], calls="operations")

    # Set IAM Bindings
    config = GConfig(config=config)
    if config.bindings:
        policy_client = Client("cloudfunctions", 'v1', calls='projects.locations.functions',
                               parent_schema=req_body['name'])

        log.info(f"adding IAM bindings for cloudfunction {function_name}")
        policy_bindings = {
            'policy': {'bindings': config.bindings}
        }
        resp = policy_client.execute('setIamPolicy', parent_key="resource", params={'body': policy_bindings})


def destroy_cloudfunction(name):
    """Destroys cloudfunction"""
    try:
        client = Client("cloudfunctions", 'v1', calls='projects.locations.functions', parent_schema='projects/{project_id}/locations/{location_id}/functions/' + name)
        client.execute('delete', parent_key="name")
        log.info(f"deleting google cloudfunction {name}......")
    except HttpError as e:
        if e.resp.status == 404:
            log.info(f"cloudfunction {name} already destroyed")
        else:
            raise e


def destroy_cloudfunction_artifacts(name):
    """Destroys all images stored in cloud storage that are related to the function."""
    client = Client("cloudresourcemanager", 'v1', calls='projects')
    resp = client.execute('get', parent_key='projectId', parent_schema=get_default_project())
    project_number = resp["projectNumber"]
    region = get_default_location()
    if not region:
        raise Exception("Missing Region")
    bucket_name = f"gcf-sources-{project_number}-{get_default_location()}"
    http = client.http or google_auth_httplib2.AuthorizedHttp(get_credentials())
    resp = http.request(f"https://storage.googleapis.com/storage/v1/b/{bucket_name}/o?prefix={name}")
    objects = json.loads(resp[1])
    if not objects.get("items"):
        log.info("Artifacts already deleted")
        return
    for storage in objects["items"]:
        log.info(f"Deleting artifact {storage['name']}")
        resp = http.request(f"https://storage.googleapis.com/storage/v1/b/{bucket_name}/o/{quote_plus(storage['name'])}", method="DELETE")
