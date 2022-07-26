from goblet.backends.backend import Backend
from goblet.client import VersionedClients, get_default_project, get_default_location
from goblet.common_cloud_actions import get_function_runtime


class CloudRun(Backend):
    resource_type = "cloudrun"
    supported_versions = ["v1"]  # do we support v2?

    def __init__(self, app, config={}):
        self.client = VersionedClients(app.client_versions).cloudfunctions
        self.func_path = f"projects/{get_default_project()}/locations/{get_default_location()}/services/{app.function_name}"
        super().__init__(app, self.client, self.func_path, config=config)

    def deploy(self, force=False):
        put_headers = {
            "content-type": "application/zip",
        }
        source = self._gcs_upload(self.client, put_headers, VersionedClients().run_uploader)
        # TODO start cloud build here (source already deployed)
