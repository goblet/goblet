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
)

log = logging.getLogger("goblet.deployer")
log.setLevel(logging.INFO)


def create_cloudfunction(client, req_body, config=None):
    """Creates a cloudfunction based on req_body"""
    function_name = req_body["name"].split("/")[-1]
    try:
        resp = client.execute(
            "create", parent_key="location", params={"body": req_body}
        )
        log.info(f"creating cloudfunction {function_name}")
    except HttpError as e:
        if e.resp.status == 409:
            log.info(f"updating cloudfunction {function_name}")
            resp = client.execute(
                "patch",
                parent_key="name",
                parent_schema=req_body["name"],
                params={"body": req_body},
            )
        else:
            raise e
    client.wait_for_operation(resp["name"], calls="operations")

    # Set IAM Bindings
    config = GConfig(config=config)
    if config.bindings:
        log.info(f"adding IAM bindings for cloudfunction {function_name}")
        policy_bindings = {"policy": {"bindings": config.bindings}}
        resp = client.execute(
            "setIamPolicy",
            parent_key="resource",
            parent_schema=req_body["name"],
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


def get_cloudrun_url(client, name):
    """Get the cloudrun url"""
    try:
        resp = client.execute(
            "get",
            parent_key="name",
            parent_schema="projects/{project_id}/locations/{location_id}/services/"
            + name,
        )
        return resp["status"]["url"]
    except HttpError as e:
        if e.resp.status == 404:
            log.info(f"cloudrun {name} not found")
        else:
            raise e


def get_cloudfunction_url(client, name):
    """Get the cloudrun url"""
    try:
        resp = client.execute(
            "get",
            parent_key="name",
            parent_schema="projects/{project_id}/locations/{location_id}/functions/"
            + name,
        )
        target = resp["httpsTrigger"]["url"]

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
            keys.remove("name")
            keys.remove("topic")
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
