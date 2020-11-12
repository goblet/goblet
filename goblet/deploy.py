from pathlib import Path
import zipfile
import os 
import requests
import logging
import subprocess

from google.cloud import storage

from goblet.client import Client, get_default_project
from goblet.utils import get_dir, get_g_dir
import hashlib

log = logging.getLogger('goblet.deployer')


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
        m = hashlib.md5()
        m.update(get_default_project().encode('utf-8'))
        m.update(self.config["name"].encode('utf-8'))
        m.update(b"goblet")
        return "goblet-" + m.hexdigest()

    def package(self, goblet):
        #TODO: add entrypoint
        self.zip()

    def deploy(self, goblet, config=None):

        self.zip()
        # url = self._upload_zip()
        # self.create_cloudfunction(url)
        # # TODO: get function name
        # function = "https://us-central1-plated-sunup-284701.cloudfunctions.net/goblet_test_app"
        # goblet.handlers["route"].generate_openapi_spec(function)
        # goblet.deploy()

        return goblet

    def destroy(self, goblet):
        goblet.destroy()
        #TODO: destory bucket and function

        return goblet
    
    def create_cloudfunction(self, url):
        subprocess.run([
            "gcloud",
            "functions",
            "deploy",
            self.name,
            "--source",
            url,
            "--runtime=python37",
            "--trigger-http",
            "--entry-point",
            "goblet_entrypoint",

        ])

    # def create_cloudfunction(self,source_url):
    #     req_body = {
    #         "name": self.name,
    #         "description":"created by goblet",
    #         "entryPoint": "goblet_entrypoint",
    #         "sourceUploadUrl": source_url,
    #         "httpsTrigger": {},
    #         "runtime":"python37",
    #         'timeout': '60s',
    #         'availableMemoryMb': 512

    #     }
    #     resp2 = self.function_client.execute('create',parent_key="location", params={'body':req_body})
       
    def _upload_zip(self):
        self.zipf.close()
        curr_dir = Path(__file__).parent.absolute()
        storage_client = storage.Client()
        bucket = storage_client.bucket(self.goblet_hash_name)
        try:
            storage_client.get_bucket(self.goblet_hash_name)
        except:
            storage_client.create_bucket(bucket, location="us")
        blob = bucket.blob("goblet.zip")
        blob.upload_from_filename(f"{get_dir()}/.goblet/goblet.zip")
        return f"gs://{self.goblet_hash_name}/goblet.zip"

    # google api
    # def _upload_zip(self):
    #     self.zipf.close()
    #     zip_size = os.stat('.goblet/goblet.zip').st_size
    #     with open('.goblet/goblet.zip', 'rb') as f:
    #         resp = self.function_client.execute('generateUploadUrl')
            
    #         upload_resp = requests.put(
    #             resp["uploadUrl"],
    #             data=f,
    #             headers={
    #                 "content-type": "application/zip", 
    #                 'Content-Length': str(zip_size),
    #                 "x-goog-content-length-range": "0,104857600"
    #                 }
    #         )

    #     log.info("function code uploaded")
        
    #     return resp["uploadUrl"]

    def create_zip(self):
        if not os.path.isdir(get_g_dir()):
            os.mkdir(get_g_dir())  
        return zipfile.ZipFile(get_g_dir() + '/goblet.zip', 'w', zipfile.ZIP_DEFLATED)

    def zip(self):
        self.zip_file("requirements.txt")
        self.zip_directory(get_dir() + '/*')

    def zip_file(self, filename):
        self.zipf.write(filename)

    def zip_directory(self, dir, exclude=['build', 'docs', 'examples']):
        exclusion_set = set(exclude)
        for path in Path('').rglob('*.py'):
            if not set(path.parts).intersection(exclusion_set):
                 self.zipf.write(str(path))

