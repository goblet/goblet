import base64
import hashlib
from pathlib import Path
import zipfile
import os
import logging
import warnings

import requests
from googleapiclient.errors import HttpError
from requests import request

from goblet.config import GConfig
from goblet.utils import get_g_dir, checksum


class Backend:
    """Base backend class"""

    resource_type = ""
    version = ""

    def __init__(self, app, client, func_path, config={}, zip_config=None):
        self.app = app
        self.name = app.function_name
        self.log = logging.getLogger("goblet.backend")
        self.log.setLevel(logging.INFO)
        self.zipf = None
        self.zip_path = get_g_dir() + f"/{self.name}.zip"
        self.config = GConfig(config=config)

        # specifies which files to be zipped
        self.zip_config = zip_config or {
            "include": ["*.py"],
            "exclude": ["build", "docs", "examples", "test", "tests", "venv"],
        }

        self.func_path = func_path

        self.client = client

    def _create_zip(self):
        """Creates initial goblet zipfile"""
        if not os.path.isdir(get_g_dir()):
            os.mkdir(get_g_dir())
        return zipfile.ZipFile(self.zip_path, "w", zipfile.ZIP_DEFLATED)

    def delta(self, client):
        """Compares md5 hash between local zipfile and cloudfunction already deployed"""
        self.zipf.close()
        with open(self.zip_path, "rb") as fh:
            local_checksum = base64.b64encode(checksum(fh, hashlib.md5())).decode(
                "ascii"
            )

        source_info = client.execute(
            "generateDownloadUrl", parent_key="name", parent_schema=self.func_path
        )
        resp = request("HEAD", source_info["downloadUrl"])
        deployed_checksum = resp.headers["x-goog-hash"].split(",")[-1].split("=", 1)[-1]
        modified = deployed_checksum != local_checksum
        return modified

    def _gcs_upload(self, client, headers, upload_client=None, force=False):
        self.log.info("zipping source code")
        self.zipf = self._create_zip()
        # zip with default include and exclude
        self.zip()
        if not force and self.get() and not self.delta(client):
            self.log.info("No changes detected....")
            return None
        self.log.info("uploading source zip to gs......")
        return self._upload_zip(upload_client or client, headers)

    def _upload_zip(self, client, headers=None) -> dict:
        """Uploads zipped cloudfunction using generateUploadUrl endpoint"""
        self.zipf.close()
        with open(f".goblet/{self.name}.zip", "rb") as f:
            resp = client.execute("generateUploadUrl", params={"body": {}})
            requests.put(
                resp["uploadUrl"],
                data=f,
                headers=headers,
            ).raise_for_status()

        self.log.info("function code uploaded")

        return resp

    def get(self):
        """Returns cloudfunction currently deployed or None"""
        try:
            return self.client.execute(
                "get", parent_key="name", parent_schema=self.func_path
            )
        except HttpError as e:
            if e.resp.status != 404:
                raise

    def zip(self):
        """Zips requirements.txt, python files and any additional files based on config.customFiles"""
        self._zip_file("requirements.txt")
        if self.config.main_file:
            self._zip_file(self.config.main_file, "main.py")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self._zip_directory()

    def _zip_file(self, filename, arcname=None):
        self.zipf.write(filename, arcname)

    def _zip_directory(self):
        exclusion_set = set(self.zip_config.get("exclude", []))
        globbed_files = []
        for pattern in self.zip_config.get("include", []):
            globbed_files.extend(Path("").rglob(pattern))
        for path in globbed_files:
            if not set(path.parts).intersection(exclusion_set):
                self.zipf.write(str(path))
