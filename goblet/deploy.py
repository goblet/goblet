from pathlib import Path
import zipfile
import os 
import requests
import logging
import hashlib

from google.cloud import storage
from google.api_core.exceptions import NotFound

from googleapiclient.errors import HttpError

from goblet.client import Client, get_default_project, get_default_location
from goblet.utils import get_dir, get_g_dir, get_goblet_app
from goblet.config import GConfig

log = logging.getLogger('goblet.deployer')
log.setLevel(logging.INFO)

class Deployer:

    def __init__(self, config={}):
        self.config = config
        if not config:
            self.config = {
                "name": "goblet_test_app"
            }
        self.name = self.config["name"]
        self.zipf = self.create_zip()
        self.goblet_hash_name = self.project_hash()
        self.function_client = self._create_function_client()

    def _create_function_client(self):
        return Client("cloudfunctions", 'v1',calls='projects.locations.functions', parent_schema='projects/{project_id}/locations/{location_id}')

    def project_hash(self):
        if not get_default_project():
            return None
        m = hashlib.md5()
        m.update(get_default_project().encode('utf-8'))
        m.update(self.config["name"].encode('utf-8'))
        m.update(b"goblet")
        return "goblet-" + m.hexdigest()

    def package(self, goblet):
        self.zip()

    def deploy(self, goblet, skip_function=False,only_function=False, config=None):
        if not skip_function:
            log.info("zipping function......")
            self.zip()
            log.info("uploading function zip to gs......")
            url = self._upload_zip()
            log.info("creating google function......")
            # TODO: CHECK IF VERSION IS DEPLOYED
            self.create_cloudfunction(url, goblet.entrypoint)
        function_name = f"https://{get_default_location()}-{get_default_project()}.cloudfunctions.net/{self.name}"
        if not only_function:
            log.info("deploying api......")
            goblet.handlers["route"].generate_openapi_spec(function_name)
            goblet.deploy()

        return goblet

    def destroy(self, goblet):
        goblet.destroy()

        try: 
            client = Client("cloudfunctions", 'v1',calls='projects.locations.functions', parent_schema='projects/{project_id}/locations/{location_id}/functions/'+self.name)
            client.execute('delete', parent_key="name")
            log.info("deleting google cloudfunction......")
        except HttpError as e:
            if e.resp.status == 404:
                log.info(f"cloudfunction already deployed")
            else:
                raise e

        storage_client = storage.Client()
        bucket = storage_client.bucket(self.goblet_hash_name)
        try:
            bucket.delete(force=True)
            log.info("deleting storage bucket......")
        except NotFound as e:
            if e.code == 404:
                log.info(f"storage bucket already destroyed")
            else:
                raise e

        return goblet
    
    def create_cloudfunction(self,url, entrypoint):
        config = GConfig()
        user_configs = config.cloudfunction or {}
        req_body = {
            "name": f"projects/{get_default_project()}/locations/{get_default_location()}/functions/{self.name}",
            "description": config.description or "created by goblet",
            "entryPoint": entrypoint,
            "sourceUploadUrl": url,
            "httpsTrigger": {},
            "runtime":"python37",
            **user_configs
        }
        try:
            self.function_client.execute('create',parent_key="location", params={'body':req_body})
        except HttpError as e:
            if e.resp.status == 409:
                log.info(f"updating cloudfunction...")
                self.function_client.execute('patch',parent_key="name",parent_schema=req_body["name"], params={'body':req_body})
            else:
                raise e
    # def _upload_zip(self):
    #     self.zipf.close()
    #     curr_dir = Path(__file__).parent.absolute()
    #     storage_client = storage.Client()
    #     bucket = storage_client.bucket(self.goblet_hash_name)
    #     try:
    #         storage_client.get_bucket(self.goblet_hash_name)
    #     except:
    #         storage_client.create_bucket(bucket, location="us")
    #     blob = bucket.blob("goblet.zip")
    #     blob.upload_from_filename(f"{get_dir()}/.goblet/goblet.zip")
    #     return f"gs://{self.goblet_hash_name}/goblet.zip"

    # google api
    def _upload_zip(self):
        self.zipf.close()
        zip_size = os.stat('.goblet/goblet.zip').st_size
        with open('.goblet/goblet.zip', 'rb') as f:
            resp = self.function_client.execute('generateUploadUrl')
            
            upload_resp = requests.put(
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
        if not os.path.isdir(get_g_dir()):
            os.mkdir(get_g_dir())  
        return zipfile.ZipFile(get_g_dir() + '/goblet.zip', 'w', zipfile.ZIP_DEFLATED)

    def zip(self):
        config = GConfig()
        self.zip_file("requirements.txt")
        include = config.customFiles or []
        include.append('*.py')
        self.zip_directory(get_dir() + '/*', include=include)

    def zip_file(self, filename):
        self.zipf.write(filename)

    def zip_directory(self, dir, include=['*.py'], exclude=['build', 'docs', 'examples']):
        exclusion_set = set(exclude)
        globbed_files = []
        for pattern in include:
            globbed_files.extend(Path('').rglob(pattern))
        for path in globbed_files:
            if not set(path.parts).intersection(exclusion_set):
                 self.zipf.write(str(path))

