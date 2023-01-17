import os
import time
import google.auth
import google.auth.transport.requests
import google_auth_httplib2
from google.api_core.client_options import ClientOptions
from googleapiclient.discovery import build
from goblet.test_utils import HttpRecorder, HttpReplay, DATA_DIR
from googleapiclient.errors import UnknownApiNameOrVersion
import logging

log = logging.getLogger("goblet.client")
log.setLevel(logging.INFO)

DEFAULT_CLIENT_VERSIONS = {
    "cloudfunctions": "v1",
    "cloudbuild": "v1",
    "run": "v2",
    "pubsub": "v1",
    "apigateway": "v1",
    "cloudscheduler": "v1",
    "redis": "v1",
    "vpcaccess": "v1",
    "bigquery": "v2",
    "bigqueryconnection": "v1",
}


def get_default_project():
    for k in (
        "GOOGLE_PROJECT",
        "GCLOUD_PROJECT",
        "GOOGLE_CLOUD_PROJECT",
        "CLOUDSDK_CORE_PROJECT",
    ):
        if k in os.environ:
            return os.environ[k]
        try:
            _, project = google.auth.default()
            return project
        except Exception:
            return None

    return None


def get_default_project_number():
    client = Client("cloudresourcemanager", "v1", calls="projects")
    resp = client.execute(
        "get", parent_key="projectId", parent_schema=get_default_project()
    )
    return resp["projectNumber"]


def get_default_location():
    for k in (
        "GOOGLE_ZONE",
        "GCLOUD_ZONE",
        "CLOUDSDK_COMPUTE_ZONE",
        "GOOGLE_REGION",
        "GCLOUD_REGION",
        "CLOUDSDK_COMPUTE_REGION",
        "GOOGLE_LOCATION",
        "GCLOUD_LOCATION",
    ):
        if k in os.environ:
            return os.environ[k]

    return None


def get_credentials():
    """get user credentials and save them for future use"""
    DEFAULT_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]

    if os.environ.get("GOBLET_HTTP_TEST") == "REPLAY":
        return google.auth.credentials.AnonymousCredentials()

    credentials, _ = google.auth.default(scopes=DEFAULT_SCOPES)
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    return credentials


class Client:
    def __init__(
        self,
        resource,
        version="v1",
        credentials=None,
        calls=None,
        parent_schema=None,
        regional=False,
    ):
        self.project_id = get_default_project()
        self.location_id = get_default_location()
        self.calls = calls
        self.resource = resource
        self.version = version
        self.parent_schema = parent_schema

        self.http = self.http_for_tests()
        self._credentials = credentials or get_credentials()
        if self.http:
            self.credentials = None
            self.http = google_auth_httplib2.AuthorizedHttp(
                self._credentials, http=self.http
            )
        else:
            self.credentials = self._credentials
        client_options = None
        if regional:
            endpoint = f"https://{self.location_id}-{self.resource}.googleapis.com"
            client_options = ClientOptions(api_endpoint=endpoint)
        try:
            self.client = build(
                resource,
                version,
                credentials=self.credentials,
                cache_discovery=False,
                http=self.http,
                client_options=client_options,
            )
        except UnknownApiNameOrVersion:
            # build client from document if not in static discovery
            self.client = build(
                resource,
                version,
                credentials=self.credentials,
                cache_discovery=False,
                http=self.http,
                client_options=client_options,
                discoveryServiceUrl=f"https://{self.resource}.googleapis.com/$discovery/rest?version={self.version}",
            )

        self.parent = None
        if self.parent_schema:
            self.parent = self.parent_schema.format(
                project_id=self.project_id, location_id=self.location_id
            )

    def __call__(self):
        return self.client

    def http_for_tests(self):
        """Used for recording and replaying GCP api responses in tests."""
        discovery_dir = os.path.join(DATA_DIR, "discovery")
        test_dir = os.path.join(DATA_DIR, os.environ.get("GOBLET_TEST_NAME", ""))

        if os.environ.get("GOBLET_HTTP_TEST") == "RECORD":
            return HttpRecorder(test_dir, discovery_dir)
        if os.environ.get("GOBLET_HTTP_TEST") == "REPLAY":
            return HttpReplay(test_dir, discovery_dir)
        return None

    def wait_for_operation(
        self, operation, timeout=600, calls="projects.locations.operations"
    ):
        """Helper function which calls the operation endpoint until an operation in completed"""
        done = False
        operation_client = Client(
            self.resource,
            version=self.version,
            credentials=self.credentials,
            calls=calls,
            parent_schema=operation,
        )
        count = 0
        sleep_duration = 4
        while not done or count > timeout:
            resp = operation_client.execute("get", parent_key="name")
            done = resp.get("done")
            time.sleep(sleep_duration)
            count += sleep_duration
        if count > timeout:
            log.info("Timeout exceeded in wait_for_operation")
            return None
        return resp

    def execute(
        self,
        api,
        calls=None,
        parent_schema=None,
        parent=True,
        parent_key="parent",
        params=None,
    ):
        """Executes the GCP client api call. parent_schema is the name or parent param required for most api calls. project
        and location is automatically added if the schema contains {project_id} or {location_id}. The parent_key is used if
        the api call uses a different key than parent"""
        api_chain = self.client
        _params = params or {}
        _calls = calls or self.calls
        if parent_schema:
            parent_schema = parent_schema.format(
                project_id=self.project_id, location_id=self.location_id
            )
        _schema = parent_schema or self.parent

        if isinstance(_calls, str):
            calls = _calls.split(".")
        for call in calls:
            api_chain = getattr(api_chain, call)()

        if _schema and parent:
            _params[parent_key] = _schema
        return getattr(api_chain, api)(**_params).execute()


# Clients


class VersionedClients:
    def __init__(self, client_versions=DEFAULT_CLIENT_VERSIONS):
        self.client_versions = client_versions

    @property
    def cloudfunctions(self):
        return Client(
            "cloudfunctions",
            self.client_versions.get("cloudfunctions", "v1"),
            calls="projects.locations.functions",
            parent_schema="projects/{project_id}/locations/{location_id}",
        )

    @property
    def cloudbuild(self):
        return Client(
            "cloudbuild",
            self.client_versions.get("cloudbuild", "v1"),
            calls="projects.builds",
            parent_schema="projects/{project_id}/locations/{location_id}",
        )

    @property
    def run(self):
        return Client(
            "run",
            self.client_versions.get("run", "v2"),
            calls="projects.locations.services",
            parent_schema="projects/{project_id}/locations/{location_id}",
        )

    @property
    def run_job(self):
        """Only v1 is supported currently"""
        return Client(
            "run",
            "v1",
            calls="namespaces.jobs",
            parent_schema="namespaces/{project_id}",
            regional=True,
        )

    @property
    def pubsub(self):
        return Client(
            "pubsub",
            self.client_versions.get("pubsub", "v1"),
            calls="projects.subscriptions",
            parent_schema="projects/{project_id}",
        )

    @property
    def apigateway(self):
        return Client(
            "apigateway",
            self.client_versions.get("apigateway", "v1"),
            calls="projects.locations.gateways",
            parent_schema="projects/{project_id}/locations/{location_id}",
        )

    @property
    def apigateway_configs(self):
        return Client(
            "apigateway",
            self.client_versions.get("apigateway", "v1"),
            calls="projects.locations.apis.configs",
            parent_schema="projects/{project_id}/locations/{location_id}",
        )

    @property
    def apigateway_api(self):
        return Client(
            "apigateway",
            self.client_versions.get("apigateway", "v1"),
            calls="projects.locations.apis",
            parent_schema="projects/{project_id}/locations/global",
        )

    @property
    def cloudscheduler(self):
        return Client(
            "cloudscheduler",
            self.client_versions.get("cloudscheduler", "v1"),
            calls="projects.locations.jobs",
            parent_schema="projects/{project_id}/locations/{location_id}",
        )

    @property
    def eventarc(self):
        return Client(
            "eventarc",
            self.client_versions.get("eventarc", "v1"),
            calls="projects.locations.triggers",
            parent_schema="projects/{project_id}/locations/{location_id}",
        )

    @property
    def redis(self):
        return Client(
            "redis",
            self.client_versions.get("redis", "v1"),
            calls="projects.locations.instances",
            parent_schema="projects/{project_id}/locations/{location_id}",
        )

    @property
    def vpcconnector(self):
        return Client(
            "vpcaccess",
            self.client_versions.get("vpcaccess", "v1"),
            calls="projects.locations.connectors",
            parent_schema="projects/{project_id}/locations/{location_id}",
        )

    @property
    def bigquery_connections(self):
        return Client(
            "bigqueryconnection",
            self.client_versions.get("bigqueryconnection", "v1"),
            calls="projects.locations.connections",
            parent_schema="projects/{project_id}/locations/{location_id}",
        )

    @property
    def run_uploader(self):
        return Client(
            "cloudfunctions",
            "v2beta",
            calls="projects.locations.functions",
            parent_schema="projects/{project_id}/locations/{location_id}",
        )

    @property
    def bigquery_routines(self):
        return Client(
            "bigquery",
            self.client_versions.get("bigquery", "v2"),
            calls="routines",
            parent_schema="{project_id}",
        )

    @property
    def monitoring_alert(self):
        return Client(
            "monitoring",
            self.client_versions.get("monitoring", "v3"),
            calls="projects.alertPolicies",
            parent_schema="projects/{project_id}",
        )

    @property
    def logging_metric(self):
        return Client(
            "logging",
            self.client_versions.get("logging", "v2"),
            calls="projects.metrics",
            parent_schema="projects/{project_id}",
        )
