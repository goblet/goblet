import google_auth_httplib2
import logging
import json
from urllib.parse import quote_plus
from googleapiclient.errors import HttpError

from goblet.config import GConfig
from goblet.client import (
    Client,
    get_default_project,
    get_default_location,
    get_credentials,
    get_default_project_number,
)
from goblet.errors import GobletError
from goblet.utils import get_python_runtime

log = logging.getLogger("goblet.deployer")
log.setLevel(logging.INFO)


def create_cloudfunctionv1(client: Client, params: dict, config=None):
    create_cloudfunction(
        client, params, config, parent_key="location", operations_calls="operations"
    )


def create_cloudfunctionv2(client: Client, params: dict, config=None):
    create_cloudfunction(
        client,
        params,
        config,
        parent_key="parent",
        operations_calls="projects.locations.operations",
    )


def create_cloudfunction(
    client: Client,
    params: dict,
    config=None,
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
    config = config or GConfig(config=config)
    if config.bindings:
        log.info(f"adding IAM bindings for cloudfunction {function_name}")
        policy_bindings = {"policy": {"bindings": config.bindings}}
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
    cloudbuild_config = GConfig().cloudbuild or {}
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


# calls latest build and checks for its artifact to avoid image:latest behavior with cloud run revisions
def getCloudbuildArtifact(client, artifactName, config):
    defaultProject = get_default_project()
    resp = client.execute(
        "list", parent_key="projectId", parent_schema=defaultProject, params={}
    )

    # search for latest build with artifactName
    latestArtifact = None
    build_configs = config.cloudbuild or {}
    registry = (
        build_configs.get("artifact_registry")
        or f"{get_default_location()}-docker.pkg.dev/{get_default_project()}/cloud-run-source-deploy/{artifactName}"
    )

    for build in resp["builds"]:
        # pending builds will not have results field.
        if (
            build.get("results")
            and build["results"].get("images")
            and registry == build["results"]["images"][0]["name"]
        ):
            latestArtifact = latestArtifact = (
                build["results"]["images"][0]["name"]
                + "@"
                + build["results"]["images"][0]["digest"]
            )
            break

    if not latestArtifact:
        raise MissingArtifact("Missing artifact. Cloud Build may have failed.")
    return latestArtifact


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


def create_pubsub_subscription(client, sub_name, req_body):
    """Creates a pubsub subscription from req_body"""
    try:
        client.execute(
            "create",
            parent_key="name",
            parent_schema="projects/{project_id}/subscriptions/" + sub_name,
            params={"body": req_body},
        )
        log.info(f"creating pubsub subscription {sub_name}")
    except HttpError as e:
        if e.resp.status == 409:
            log.info(f"updating pubsub subscription {sub_name}")
            # Setup update mask
            keys = list(req_body.keys())
            # Remove keys that cannot be updated
            keys.remove("name")
            keys.remove("topic")
            keys.remove("filter")
            keys.remove("enableMessageOrdering")
            updateMask = ",".join(keys)
            client.execute(
                "patch",
                parent_key="name",
                parent_schema="projects/{project_id}/subscriptions/" + sub_name,
                params={"body": {"subscription": req_body, "updateMask": updateMask}},
            )
        else:
            raise e


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
