import base64
import hashlib
import logging
import os

import requests
from requests import request

from googleapiclient.errors import HttpError

from goblet.backends.backend import Backend
from goblet.client import VersionedClients, get_default_location, get_default_project
from goblet.common_cloud_actions import get_function_runtime, create_cloudfunction


class CloudFunctionV1(Backend):
    resource_type = "cloudfunction"
    supported_versions = ["v1"]

    def __init__(self, app, config={}):
        self.client = VersionedClients(app.client_versions).cloudfunctions
        self.func_path = f"projects/{get_default_project()}/locations/{get_default_location()}/functions/{app.function_name}"
        super().__init__(app, self.client, self.func_path, config=config)

    def deploy(self, force=False):
        put_headers = {
            "content-type": "application/zip",
            "x-goog-content-length-range": "0,104857600",
        }
        source = self._gcs_upload(self.client, put_headers, force=force)
        if self.app.is_http():
            client, params = self._get_upload_params(source)
            create_cloudfunction(client, params, config=self.config)

    def _get_upload_params(self, source):
        user_configs = self.config.cloudfunction or {}
        params = {
            "body": {
                "name": self.func_path,
                "description": self.config.description or "created by goblet",
                "entryPoint": "goblet_entrypoint",
                "sourceUploadUrl": source["uploadUrl"],
                "httpsTrigger": {},
                "runtime": get_function_runtime(self.client, self.config),
                **user_configs,
            }
        }
        return self.client, params







