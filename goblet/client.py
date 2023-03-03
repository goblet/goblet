import logging
from goblet_gcp_client import Client
from goblet_gcp_client.client import get_default_project

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
    "secretmanager": "v1",
}


def get_default_project_number():
    client = Client("cloudresourcemanager", "v1", calls="projects")
    resp = client.execute(
        "get", parent_key="projectId", parent_schema=get_default_project()
    )
    return resp["projectNumber"]


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
        return Client(
            "run",
            self.client_versions.get("run", "v2"),
            calls="projects.locations.jobs",
            parent_schema="projects/{project_id}/locations/{location_id}",
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

    @property
    def secretmanager(self):
        return Client(
            "secretmanager",
            self.client_versions.get("secretmanager", "v1"),
            calls="projects.secrets.versions",
            parent_schema="projects/{project_id}",
        )
