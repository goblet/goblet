import google_auth_httplib2
import logging
import json
from urllib.parse import quote_plus
import base64
from googleapiclient.errors import HttpError

import goblet.globals as g
import os
from goblet.client import (
    VersionedClients,
    get_default_project_number,
)
from goblet_gcp_client.client import (
    Client,
    get_default_location,
    get_credentials,
    get_default_project,
)
from goblet.errors import GobletError
from goblet.utils import get_python_runtime
from goblet.permissions import add_binding
from typing import List

log = logging.getLogger("goblet.deployer")
log.setLevel(logging.getLevelName(os.getenv("GOBLET_LOG_LEVEL", "INFO")))


def check_or_enable_service(resources: List[str], enable: bool = False):
    if len(resources) == 0:
        return
    client = VersionedClients().service_usage
    if enable:
        resp = client.execute(
            "batchEnable",
            parent_key="parent",
            parent_schema="projects/{project_id}",
            params={
                "body": {
                    "serviceIds": [
                        f"{resource}.googleapis.com" for resource in resources
                    ]
                }
            },
        )
        if not resp.get("done"):
            client.wait_for_operation(resp["name"], calls="operations")
        for resource in resources:
            log.info(f"{resource} enabled")
    else:
        resp = client.execute(
            "batchGet",
            parent_key="parent",
            parent_schema="projects/{project_id}",
            params={
                "names": [
                    f"projects/{get_default_project()}/services/{resource}.googleapis.com"
                    for resource in resources
                ]
            },
        )
        for service in resp["services"]:
            log.info(f"{service['config']['name']} {service['state']}")
    return None


####### Cloud Functions #######
def create_cloudfunctionv1(client: Client, params: dict, config=None):
    create_cloudfunction(
        client, params, parent_key="location", operations_calls="operations"
    )


def create_cloudfunctionv2(client: Client, params: dict):
    create_cloudfunction(
        client,
        params,
        parent_key="parent",
        operations_calls="projects.locations.operations",
    )


def create_cloudfunction(
    client: Client,
    params: dict,
    parent_key="location",
    operations_calls="operations",
):
    """Creates a cloudfunction based on req_body"""
    function_name = params["body"]["name"].split("/")[-1]
    try:
        resp = client.execute("create", parent_key=parent_key, params=params)
        log.info(f"creating cloudfunction {function_name}")
    except HttpError as e:
        if e.resp.status == 409:
            log.info(f"updating cloudfunction {function_name}")
            resp = client.execute(
                "patch",
                parent_key="name",
                parent_schema=params["body"]["name"],
                params={"body": params["body"]},
            )
        else:
            raise e

    client.wait_for_operation(resp["name"], calls=operations_calls)

    # Set IAM Bindings
    if g.config.bindings:
        log.info(f"adding IAM bindings for cloudfunction {function_name}")
        policy_bindings = {"policy": {"bindings": g.config.bindings}}
        resp = client.execute(
            "setIamPolicy",
            parent_key="resource",
            parent_schema=params["body"]["name"],
            params={"body": policy_bindings},
        )


def destroy_cloudfunction(client, name):
    """Destroys cloudfunction"""
    try:
        client.execute(
            "delete",
            parent_schema="projects/{project_id}/locations/{location_id}/functions/"
            + name,
            parent_key="name",
        )
        log.info(f"deleting google cloudfunction {name}......")
    except HttpError as e:
        if e.resp.status == 404:
            log.info(f"cloudfunction {name} already destroyed")
        else:
            raise e


def destroy_cloudfunction_artifacts(name):
    """Destroys all images stored in cloud storage that are related to the function."""
    client = Client("cloudresourcemanager", "v1", calls="projects")
    resp = client.execute(
        "get", parent_key="projectId", parent_schema=get_default_project()
    )
    project_number = resp["projectNumber"]
    region = get_default_location()
    if not region:
        raise Exception("Missing Region")
    bucket_name = f"gcf-sources-{project_number}-{get_default_location()}"
    http = client.http or google_auth_httplib2.AuthorizedHttp(get_credentials())
    resp = http.request(
        f"https://storage.googleapis.com/storage/v1/b/{bucket_name}/o?prefix={name}"
    )
    objects = json.loads(resp[1])
    if not objects.get("items"):
        log.info("Artifacts already deleted")
        return
    for storage in objects["items"]:
        log.info(f"Deleting artifact {storage['name']}")
        resp = http.request(
            f"https://storage.googleapis.com/storage/v1/b/{bucket_name}/o/{quote_plus(storage['name'])}",
            method="DELETE",
        )


def get_cloudfunction_url(client, name):
    """Get the cloudrun url"""
    if client.version == "v1":
        return f"https://{get_default_location()}-{get_default_project()}.cloudfunctions.net/{name}"
    try:
        resp = client.execute(
            "get",
            parent_key="name",
            parent_schema="projects/{project_id}/locations/{location_id}/functions/"
            + name,
        )
        # handle both cases: first for gcf v1 and second for v2
        try:
            target = resp["httpsTrigger"]["url"]
        except KeyError:
            target = resp["serviceConfig"]["uri"]
        return target
    except HttpError as e:
        if e.resp.status == 404:
            log.info(f"cloudfunction {name} not found")
        else:
            raise e


def get_function_runtime(client, config=None):
    """
    Returns the proper runtime to be used in cloudfunctions
    """
    runtime = config.runtime or get_python_runtime()
    required_runtime = "python37" if client.version == "v1" else "python38"
    if int(runtime.split("python")[-1]) < int(required_runtime.split("python")[-1]):
        raise ValueError(
            f"Your current python runtime is {runtime}. Your backend requires a minimum of {required_runtime}"
            f". Either upgrade python on your machine or set the 'runtime' field in config.json."
        )
    return runtime


####### Cloud Run #######


def destroy_cloudrun(client, name):
    """Destroys cloudrun"""
    try:
        client.execute(
            "delete",
            parent_schema="projects/{project_id}/locations/{location_id}/services/"
            + name,
            parent_key="name",
        )
        log.info(f"deleting cloudrun {name}......")
    except HttpError as e:
        if e.resp.status == 404:
            log.info(f"cloudrun {name} already destroyed")
        else:
            raise e


def deploy_cloudrun(client, req_body, name):
    """Deploys cloud build to cloudrun"""
    try:
        params = {"body": req_body, "serviceId": name}
        resp = client.execute(
            "create",
            parent_key="parent",
            parent_schema="projects/"
            + get_default_project_number()
            + "/locations/{location_id}",
            params=params,
        )
        log.info("creating cloudrun")
    except HttpError as e:
        if e.resp.status == 409:
            log.info("updating cloudrun")
            resp = client.execute(
                "patch",
                parent_key="name",
                parent_schema="projects/"
                + get_default_project_number()
                + "/locations/{location_id}/services/"
                + name,
                params={"body": req_body},
            )
        else:
            raise e
    client.wait_for_operation(resp["name"], calls="projects.locations.operations")


def get_cloudrun_url(client, name):
    """Get the cloudrun url"""
    try:
        resp = client.execute(
            "get",
            parent_key="name",
            parent_schema="projects/{project_id}/locations/{location_id}/services/"
            + name,
        )
        # Handle both cases: cloudrun v1 and v2
        try:
            target = resp["status"]["url"]
        except KeyError:
            target = resp["uri"]
        return target
    except HttpError as e:
        if e.resp.status == 404:
            log.info(f"cloudrun {name} not found")
        else:
            raise e


####### Cloud Build #######


def create_cloudbuild(client, req_body):
    """Creates a cloudbuild based on req_body"""
    defaultProject = get_default_project()
    defaultLocation = "global"
    try:
        resp = client.execute(
            "create",
            parent_key="projectId",
            parent_schema=defaultProject,
            params={
                "body": req_body,
                "parent": f"projects/{defaultProject}/locations/{defaultLocation}",
            },
        )
        log.info("creating cloudbuild")
    except HttpError as e:
        raise e
    cloudbuild_config = g.config.cloudbuild or {}
    timeout_seconds = cloudbuild_config.get("timeout", "600s")
    if "s" not in timeout_seconds:
        log.info(
            "Not a valid timeout. Needs to be a duration that ends is 's'. Defaulting to 600s"
        )
        timeout = 600
    else:
        timeout = int(timeout_seconds.split("s")[0])
    resp = client.wait_for_operation(resp["name"], calls="operations", timeout=timeout)
    if not resp:
        raise GobletError("Build Timed out")
    if resp.get("error"):
        raise GobletError(
            f"Cloud build failed with error code {resp['error']['code']} and message {resp['error']['message']}"
        )


class MissingArtifact(Exception):
    """Raised when missing Cloudrun Artifact."""

    def __init__(self, missing):
        self.missing = missing


def getDefaultRegistry(artifactName):
    return f"{get_default_location()}-docker.pkg.dev/{get_default_project()}/cloud-run-source-deploy/{artifactName}"


def getDefaultRegistryName():
    return f"projects/{get_default_project()}/locations/{get_default_location()}/repositories/cloud-run-source-deploy"


# calls latest build and checks for its artifact to avoid image:latest behavior with cloud run revisions
def getCloudbuildArtifact(client, artifactName, config):
    defaultProject = get_default_project()
    resp = client.execute(
        "list", parent_key="projectId", parent_schema=defaultProject, params={}
    )

    # search for latest build with artifactName
    latestArtifact = None
    try:
        registry = config.deploy.get("artifact_registry") or getDefaultRegistry(
            artifactName
        )
    except AttributeError:
        registry = getDefaultRegistry(artifactName)

    for build in resp["builds"]:
        # pending builds will not have results field.
        if (
            build.get("results")
            and build["results"].get("images")
            and registry == build["results"]["images"][0]["name"]
        ):
            latestArtifact = (
                build["results"]["images"][0]["name"]
                + "@"
                + build["results"]["images"][0]["digest"]
            )
            break

    if not latestArtifact:
        raise MissingArtifact("Missing artifact. Cloud Build may have failed.")
    return latestArtifact


####### Pub Sub #######


def get_pubsub_subscription(client, sub_name, req_body):
    try:
        resp = client.execute(
            "get",
            parent_key="subscription",
            parent_schema="projects/{project_id}/subscriptions/" + sub_name,
        )
    except HttpError as e:
        if e.resp.status == 404:
            return None
    return resp


def create_pubsub_subscription(client, sub_name, req_body, force_update=False):
    """Creates a pubsub subscription from req_body"""
    response = get_pubsub_subscription(client, sub_name, req_body)
    if response and response["topic"] != req_body["topic"]:
        log.info(
            f"Pubsub subscription projects do not match. {sub_name} is currently subscribed to {response['topic']}, but defined to be {req_body['topic']}."
        )
        if force_update:
            log.info("force_update is set to True. Deleting existing subscrition...")
            destroy_pubsub_subscription(client, sub_name)
            response = None
        else:
            log.info("force_update is set to False. Skipping update...")
            return

    # create pubsub
    if not response:
        client.execute(
            "create",
            parent_key="name",
            parent_schema="projects/{project_id}/subscriptions/" + sub_name,
            params={"body": req_body},
        )
        log.info(f"creating pubsub subscription {sub_name}")

    # update
    else:
        log.info(f"updating pubsub subscription {sub_name}")

        # Setup update mask
        keys = list(req_body.keys())
        # Remove keys that cannot be updated
        keys.remove("topic")
        if "filter" in keys:
            keys.remove("filter")
        if "labels" in keys:
            if req_body["labels"] is None or req_body["labels"] == {}:
                keys.remove("labels")
        if "enableMessageOrdering" in keys:
            keys.remove("enableMessageOrdering")
        updateMask = ",".join(keys)
        client.execute(
            "patch",
            parent_key="name",
            parent_schema="projects/{project_id}/subscriptions/" + sub_name,
            params={"body": {"subscription": req_body, "updateMask": updateMask}},
        )


def destroy_pubsub_subscription(client, name):
    """Destroys pubsub subscription"""
    try:
        client.execute(
            "delete",
            parent_key="subscription",
            parent_schema="projects/{project_id}/subscriptions/" + name,
        )
        log.info(f"deleting pubsub subscription {name}......")
    except HttpError as e:
        if e.resp.status == 404:
            log.info(f"pubsub subscription {name} already destroyed")
        else:
            raise e


####### Event Arc #######


def create_eventarc_trigger(client, trigger_name, region, req_body):
    """Creates an eventarc trigger from req_body"""
    try:
        client.execute(
            "create",
            parent_key="parent",
            parent_schema="projects/{project_id}/locations/" + region,
            params={"body": req_body, "triggerId": trigger_name, "validateOnly": False},
        )
        log.info(f"creating eventarc trigger {trigger_name}")
    except HttpError as e:
        if e.resp.status == 409:
            log.info(f"updating eventarc trigger  {trigger_name}")
            # Setup update mask
            keys = list(req_body.keys())
            keys.remove("name")
            if "transport" in keys:
                keys.remove("transport")
            updateMask = ",".join(keys)
            client.execute(
                "patch",
                parent_key="name",
                parent_schema="projects/{project_id}/locations/"
                + region
                + "/triggers/"
                + trigger_name,
                params={"body": req_body, "updateMask": updateMask},
            )
        else:
            raise e


def destroy_eventarc_trigger(client, trigger_name, region):
    """Destroys eventarc trigger"""
    try:
        client.execute(
            "delete",
            parent_key="name",
            parent_schema="projects/{project_id}/locations/"
            + region
            + "/triggers/"
            + trigger_name,
        )
        log.info(f"deleting eventarc trigger  {trigger_name}......")
    except HttpError as e:
        if e.resp.status == 404:
            log.info(f"eventarc trigger  {trigger_name} already destroyed")
        else:
            raise e


####### Api Gateway #######


def deploy_apigateway(name, gconfig, versioned_clients, spec_path):
    "Deploy an Api, Api Gateway, & Api Config"
    try:
        resp = versioned_clients.apigateway_api.execute(
            "create",
            params={"apiId": name, "body": {"labels": gconfig.labels}},
        )
        versioned_clients.apigateway_api.wait_for_operation(resp["name"])
    except HttpError as e:
        if e.resp.status == 409:
            log.info("api already deployed")
        else:
            raise e
    config = {
        "openapiDocuments": [
            {
                "document": {
                    "path": spec_path,
                    "contents": base64.b64encode(open(spec_path, "rb").read()).decode(
                        "utf-8"
                    ),
                }
            }
        ],
        "labels": gconfig.labels,
        **(gconfig.apiConfig or {}),
    }
    try:
        config_version_name = name
        versioned_clients.apigateway_configs.execute(
            "create",
            params={"apiConfigId": name, "body": config},
            parent_schema="projects/{project_id}/locations/global/apis/" + name,
        )
    except HttpError as e:
        if e.resp.status == 409:
            log.info("updating api endpoints")
            configs = versioned_clients.apigateway_configs.execute(
                "list",
                parent_schema="projects/{project_id}/locations/global/apis/" + name,
            )
            # TODO: use hash
            version = len(configs["apiConfigs"])
            config_version_name = f"{name}-v{version}"
            versioned_clients.apigateway_configs.execute(
                "create",
                parent_schema="projects/{project_id}/locations/global/apis/" + name,
                params={"apiConfigId": config_version_name, "body": config},
            )
        else:
            raise e
    gateway = {
        "apiConfig": f"projects/{get_default_project()}/locations/global/apis/{name}/configs/{config_version_name}",
        "labels": gconfig.labels,
    }
    try:
        gateway_resp = versioned_clients.apigateway.execute(
            "create", params={"gatewayId": name, "body": gateway}
        )
    except HttpError as e:
        if e.resp.status == 409:
            log.info("updating gateway")
            gateway_resp = versioned_clients.apigateway.execute(
                "patch",
                parent_key="name",
                parent_schema="projects/{project_id}/locations/{location_id}/gateways/"
                + name,
                params={"updateMask": "apiConfig", "body": gateway},
            )
        else:
            raise e
    if gateway_resp:
        versioned_clients.apigateway.wait_for_operation(gateway_resp["name"])
    log.info("api successfully deployed...")
    gateway_resp = versioned_clients.apigateway.execute(
        "get",
        parent_key="name",
        parent_schema="projects/{project_id}/locations/{location_id}/gateways/" + name,
    )
    log.info(f"api endpoint is {gateway_resp['defaultHostname']}")


def destroy_apigateway(name, versioned_clients):
    """Destroy api gateway"""
    try:
        resp = versioned_clients.apigateway.execute(
            "delete",
            parent_schema="projects/{project_id}/locations/{location_id}/gateways/"
            + name,
            parent_key="name",
        )
        log.info("destroying api gateway......")
        versioned_clients.apigateway_configs.wait_for_operation(resp["name"])
    except HttpError as e:
        if e.resp.status == 404:
            log.info("api gateway already destroyed")
        else:
            raise e
    # destroy api config
    try:
        configs = versioned_clients.apigateway_configs.execute(
            "list",
            parent_schema="projects/{project_id}/locations/global/apis/" + name,
        )
        resp = {}
        log.info("api configs destroying....")
        for c in configs.get("apiConfigs", []):
            resp = versioned_clients.apigateway_configs.execute(
                "delete",
                parent_key="name",
                parent_schema="projects/{project_id}/locations/global/apis/"
                + name
                + "/configs/"
                + c["displayName"],
            )
            if resp:
                versioned_clients.apigateway_configs.wait_for_operation(resp["name"])
    except HttpError as e:
        if e.resp.status == 404:
            log.info("api configs already destroyed")
        else:
            raise e

    # destroy api
    try:
        resp = versioned_clients.apigateway_api.execute(
            "delete",
            parent_key="name",
            parent_schema="projects/{project_id}/locations/global/apis/" + name,
        )
        versioned_clients.apigateway_configs.wait_for_operation(resp["name"])
        log.info("apis successfully destroyed......")
    except HttpError as e:
        if e.resp.status == 404:
            log.info("api already destroyed")
        else:
            raise e


####### IAM #######


def deploy_custom_role(client, role):
    """Deploys a custom iam role"""
    try:
        params = {"body": role}
        resp = client.execute(
            "create",
            parent_key="parent",
            parent_schema="projects/" + get_default_project(),
            params=params,
        )
        log.info(f"creating custom iam role {role['roleId']}...")
    except HttpError as e:
        if e.resp.status == 409:
            log.info(f"updating custom iam role {role['roleId']}...")
            resp = client.execute(
                "patch",
                parent_key="name",
                parent_schema="projects/"
                + get_default_project()
                + "/roles/"
                + role["roleId"],
                params={"body": role["role"], "updateMask": "includedPermissions"},
            )
        else:
            raise e
    return resp


def deploy_service_account(versioned_client, name, roleName):
    """Deploys service account with custom role.
    Service Account name needs to be [a-zA-Z][a-zA-Z-]*[a-zA-Z]
    """
    try:
        params = {
            "body": {
                "accountId": name,
                "serviceAccount": {
                    "displayName": name,
                    "description": "generated by goblet",
                },
            }
        }
        versioned_client.service_account.execute(
            "create",
            parent_key="name",
            parent_schema="projects/" + get_default_project(),
            params=params,
        )
        log.info(f"creating service account {name}...")
    except HttpError as e:
        if e.resp.status == 409:
            log.info(f"service account {name} already exists...")
        else:
            raise e
    add_binding(
        versioned_client.project_resource_manager,
        "projects/" + get_default_project(),
        f"projects/{get_default_project()}/roles/{roleName}",
        [f"serviceAccount:{name}@{get_default_project()}.iam.gserviceaccount.com"],
    )
