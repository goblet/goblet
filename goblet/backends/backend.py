import base64
import hashlib
import logging
import os
import warnings
import zipfile
from pathlib import Path

import requests
from googleapiclient.errors import HttpError

import goblet.globals as g
from goblet.utils import get_g_dir, checksum, build_stage_config
from goblet.common_cloud_actions import check_or_enable_service


class Backend:
    """Base backend class"""

    resource_type = ""
    version = ""
    required_files = ["main.py"]
    config_key = ""
    monitoring_type = ""
    monitoring_label_key = ""
    required_apis = []
    permissions = []

    def __init__(self, app, client, func_path):
        self.app = app
        self.name = app.function_name
        self.log = logging.getLogger("goblet.backend")
        self.log.setLevel(logging.getLevelName(os.getenv("GOBLET_LOG_LEVEL", "INFO")))
        self.zip_path = get_g_dir() + f"/{self.name}.zip"
        self._zipf = None
        self.config = g.config

        # specifies which files to be zipped
        custom_files = self.config.custom_files or {}
        include = ["*.py", ".goblet/*.py", "requirements.txt"]
        exclude = ["build", "docs", "examples", "test", "tests", "venv", ".git"]

        include.extend(custom_files.get("include", []))
        exclude.extend(custom_files.get("exclude", []))

        self.zip_config = {"include": include, "exclude": exclude}

        self.func_path = func_path

        self.client = client
        self.validation_config()

    def validation_config(self):
        pass

    def deploy(self, force=False):
        raise NotImplementedError("destroy")

    def skip_deployment(self):
        return False

    def destroy(self, all=False):
        raise NotImplementedError("destroy")

    def update_config(self, infra_config={}, write_config=False, stage=None):
        raise NotImplementedError("update_config")

    @property
    def zipf(self):
        if not self._zipf:
            self._zipf = self._create_zip()
        return self._zipf

    def _create_zip(self):
        """Creates initial goblet zipfile"""
        if not os.path.isdir(get_g_dir()):
            os.mkdir(get_g_dir())
        return zipfile.ZipFile(self.zip_path, "w", zipfile.ZIP_DEFLATED)

    def delta(self, zip_path=None):
        """Compares md5 hash between local zipfile and cloudfunction already deployed"""
        if zip_path is None:
            zip_path = self.zip_path
        self.zipf.close()
        with open(zip_path, "rb") as fh:
            local_checksum = base64.b64encode(checksum(fh, hashlib.md5())).decode(
                "ascii"
            )

        deployed_checksum = self._checksum()
        modified = deployed_checksum != local_checksum
        return modified

    def _checksum(self):
        raise NotImplementedError("_checksum")

    def _gcs_upload(self, client, headers, upload_client=None, force=False):
        self.log.info("zipping source code")
        self.zip()
        if not force and self.get() and not self.delta():
            self.log.info("No changes detected....")
            return None, False
        self.log.info("uploading source zip to gs......")
        return self._upload_zip(upload_client or client, headers), True

    def _upload_zip(self, client, headers=None) -> dict:
        """Uploads zipped cloudfunction using generateUploadUrl endpoint"""
        self.zipf.close()
        with open(f".goblet/{self.name}.zip", "rb") as f:
            resp = client.execute("generateUploadUrl", params={"body": {}})
            try:
                requests.put(
                    resp["uploadUrl"],
                    data=f,
                    headers=headers,
                ).raise_for_status()
            except requests.exceptions.HTTPError as e:
                if not os.environ.get("G_HTTP_TEST") == "REPLAY":
                    raise e

        self.log.info("source code uploaded")

        return resp

    def get(self):
        """Returns backend currently deployed or None"""
        try:
            return self.client.execute(
                "get", parent_key="name", parent_schema=self.func_path
            )
        except HttpError as e:
            if e.resp.status != 404:
                raise

    @property
    def http_endpoint(self):
        raise NotImplementedError("http_endpoint")

    def zip_required_files(self):
        """Zip required files for the specified backend"""
        self._zip_config()
        if self.config.requirements_file:
            self._zip_file(self.config.requirements_file, "requirements.txt")
        else:
            self._zip_file("requirements.txt")
        if self.config.main_file:
            self._zip_file(self.config.main_file, "main.py")

    def zip(self):
        """Zips python files and any additional files based on config.custom_files"""
        self.zip_required_files()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self._zip_directory()

    def _zip_file(self, filename, arcname=None):
        """skip files if not required and do not exist"""
        if not os.path.exists(filename) and filename not in self.required_files:
            return
        self.log.debug(f"Zipping file: {filename}...")
        self.zipf.write(filename, arcname)

    def _zip_config(self):
        config_path = ".goblet/config.json"
        stage_config_file = None
        if os.path.exists(config_path):
            if self.config.stage:
                stage_config_file = build_stage_config(
                    config_path=config_path, stage=self.config.stage
                )
                config_path = stage_config_file.name
            self.zipf.write(
                config_path, ".goblet/config.json", compress_type=zipfile.ZIP_DEFLATED
            )

        if stage_config_file:
            stage_config_file.close()

    def _zip_directory(self):
        exclusion_set = set(self.zip_config.get("exclude", []))
        globbed_files = []
        for pattern in self.zip_config.get("include", []):
            globbed_files.extend(Path("").rglob(pattern))
        for path in globbed_files:
            if not set(path.parts).intersection(exclusion_set):
                self.log.debug(f"Zipping file: {path}...")
                self.zipf.write(str(path))

    def get_environment_vars(self):
        raise NotImplementedError("get_environment_vars")

    def _check_or_enable_service(self, enable=False):
        return check_or_enable_service(self.required_apis, enable)

    def add_invoker_binding(self, principles):
        raise NotImplementedError("add_invoker_binding")
