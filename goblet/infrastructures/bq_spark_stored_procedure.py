import logging
import os
import inspect

from googleapiclient.errors import HttpError
from goblet.infrastructures.infrastructure import Infrastructure
from goblet_gcp_client.client import (
    get_default_project,
    get_default_location,
)
from goblet.permissions import gcp_generic_resource_permissions
from goblet.client import VersionedClients


log = logging.getLogger("goblet.deployer")
log.setLevel(logging.getLevelName(os.getenv("GOBLET_LOG_LEVEL", "INFO")))


class BigQuerySparkStoredProcedure(Infrastructure):
    """
    Cloud Big Query Spark Stored procedures.
    https://cloud.google.com/bigquery/docs/spark-procedures

    Limitations
    https://cloud.google.com/bigquery/docs/spark-procedures#limitations

    """

    resource_type = "bqsparkstoredprocedure"
    required_apis = ["bigquery", "bigqueryconnection"]
    permissions = [
        "bigquery.jobs.create",
        "bigquery.connections.delegate",
        "bigquery.connections.use",
        *gcp_generic_resource_permissions("storage", "objects"),
        *gcp_generic_resource_permissions("storage", "buckets"),
        *gcp_generic_resource_permissions("bigquery", "connections"),
        *gcp_generic_resource_permissions("bigquery", "table"),
        *gcp_generic_resource_permissions("bigquery", "routines"),
    ]

    def register(self, name, kwargs):
        """
        Register in handler resources
        :param name: name of resource
        :param kwargs:
        :return:
        """
        config = (
            self.config.bqsparkstoredprocedure.copy()
            if self.config.bqsparkstoredprocedure
            else {}
        )
        # Routine names must contain only letters, numbers, and underscores, and be at most 256 characters long.
        routine_name = config.get("name", name).replace("-", "_")
        dataset_id = config.get("dataset_id", kwargs["dataset_id"])
        runtime_version = config.get("runtime_version", kwargs["runtime_version"])
        # Func cannot be loaded from config file as it is a function
        func = kwargs.get("func")
        spark_file = config.get("spark_file", kwargs["spark_file"])
        container_image = config.get(
            "container_image", kwargs.get("container_image", None)
        )
        additional_python_files = config.get(
            "additional_python_files", kwargs.get("additional_python_files", [])
        )
        additional_files = config.get(
            "additional_files", kwargs.get("additional_files", [])
        )
        properties = config.get("properties", kwargs.get("properties", {}))

        local_code = False
        if func is not None:
            func = self.stringify_func(func)
            local_code = True

        self.connection_location = config.get(
            "location", kwargs.get("location", get_default_location())
        )
        self.resources[routine_name] = {
            "routine_name": routine_name,
            "dataset_id": dataset_id,
            "func": func,
            "location": self.connection_location,
            "runtime_version": runtime_version,
            "spark_file": spark_file,
            "local_code": local_code,
            "container_image": container_image,
            "additional_python_files": additional_python_files,
            "additional_files": additional_files,
            "properties": properties,
        }
        return True

    def _deploy(self):
        if not self.resources:
            return
        log.info("Deploying bigquery remote functions")

        try:
            self.deploy_bigquery_connection(self.name, self.connection_location)
        except HttpError as exception:
            if exception.resp.status == 409:
                log.info("Connection already created bigquery query: for %s", self.name)
            else:
                log.error("Create connection %s", exception.error_details)
                raise exception

        for _, resource in self.resources.items():
            if not resource["local_code"]:
                self.deploy_bucket(self.name)
                resource["spark_file"] = self.upload_file(
                    resource["spark_file"], self.name
                )
                if resource["additional_python_files"]:
                    for i in range(len(resource["additional_python_files"])):
                        resource["additional_python_files"][i] = self.upload_file(
                            resource["additional_python_files"][i], self.name
                        )
                if resource["additional_files"]:
                    for i in range(len(resource["additional_files"])):
                        resource["additional_files"][i] = self.upload_file(
                            resource["additional_files"][i], self.name
                        )

            create_routine_query = self.create_routine_payload(resource)
            routine_name = resource["routine_name"]
            try:
                self.versioned_clients.bigquery_routines.execute(
                    "insert",
                    params={
                        "body": create_routine_query,
                        "projectId": get_default_project(),
                        "datasetId": resource["dataset_id"],
                    },
                    parent_key="projectId",
                )
                log.info("Created bq routine %s", routine_name)
            except HttpError as exception:
                if exception.resp.status == 409:
                    self.versioned_clients.bigquery_routines.execute(
                        "update",
                        params={
                            "body": create_routine_query,
                            "projectId": get_default_project(),
                            "datasetId": resource["dataset_id"],
                            "routineId": routine_name,
                        },
                        parent_key="projectId",
                    )
                    log.info("Updated Spark Stored Procedure %s", routine_name)
                else:
                    log.error(
                        "Bigquery Spark Stored Procedure couldn't be created "
                        "nor updated name %s with error: %s",
                        routine_name,
                        exception.error_details,
                    )
                    raise exception

    def destroy(self):
        """
        Destroy connection then destroy one by one every routine
        :return:
        """
        if not self.resources:
            return
        self.destroy_bigquery_connection()
        for _, resource in self.resources.items():
            self.destroy_routine(resource["dataset_id"], resource["routine_name"])
            if not resource["local_code"]:
                self.destroy_bucket(self.name)

    def deploy_bigquery_connection(self, connection_name, location):
        """
            Creates (or get if exists) a connection resource with Handler.name
        :param connection_name: name for the connection
        :return:
        """
        connection_id = f"{self.name}"
        resource_type = {"spark": {}}
        try:
            bq_connection = self.versioned_clients.bigquery_connections.execute(
                "create",
                params={"body": resource_type, "connectionId": connection_id},
                parent_schema=f"projects/{get_default_project()}/locations/{location}",
            )
            log.info(f"Created bigquery connection name: {connection_id}")

        except HttpError as exception:
            if exception.resp.status == 409:
                log.info(
                    f"Bigquery connection already exist with name: {connection_name} for {self.name} and location {location}"
                )
                client = self.versioned_clients.bigquery_connections
                bq_connection = client.execute(
                    "get",
                    params={"name": client.parent + "/connections/" + connection_id},
                    parent=False,
                )
                log.info(f"Returning connection {bq_connection['name']}")
            else:
                log.error(exception.error_details)
                raise exception
        return bq_connection

    def destroy_bigquery_connection(self):
        """
        Destroy bigquery connection, if already exist do nothing
        :return:
        """
        client = self.versioned_clients.bigquery_connections
        try:
            client.execute(
                "delete",
                params={
                    "name": f"projects/{get_default_project()}/locations/{self.connection_location}"
                    + "/connections/"
                    + self.name
                },
                parent=False,
            )
        except HttpError as exception:
            if exception.resp.status == 404:
                log.info(f"Connection {self.name} already destroyed")
            else:
                raise exception
        return True

    def destroy_routine(self, dataset_id, routine_id):
        """
        :param dataset_id:
        :param routine_id:
        """
        try:
            self.versioned_clients.bigquery_routines.execute(
                "delete",
                params={
                    "projectId": get_default_project(),
                    "datasetId": dataset_id,
                    "routineId": routine_id,
                },
                parent=False,
            )
            log.info(f"Destroyed routine {routine_id} for dataset {dataset_id}")
        except HttpError as exception:
            if exception.resp.status == 409:
                log.info(f"Routine {routine_id} already destroyed")
            elif exception.resp.status == 404:
                log.info(f"Routine {routine_id} doesn't exist. already destroyed?")
            else:
                log.error(
                    f"Couldn't destroy {routine_id} for dataset {dataset_id}. {exception.error_details}"
                )
                raise exception

    def create_routine_payload(self, resource):
        """
        Create a routine object according to BigQuery specification
        :param resource: a resource saved in resources in Handler
        :return: a dict representing a routine according to
                https://cloud.google.com/bigquery/docs/reference/rest/v2/routines
        """
        spark_options = {
            "connection": f"projects/{get_default_project()}/locations/{resource['location']}/connections/{self.name}",
            "runtimeVersion": resource["runtime_version"],
            "containerImage": resource["container_image"],
            "properties": resource["properties"],
        }
        routine_reference = {
            "projectId": get_default_project(),
            "datasetId": resource["dataset_id"],
            "routineId": resource["routine_name"],
        }
        language = "PYTHON"

        query_request = {
            "language": language,
            "routineReference": routine_reference,
            "routineType": "PROCEDURE",
            "sparkOptions": spark_options,
        }

        if resource["local_code"]:
            query_request["definitionBody"] = resource["func"]
        else:
            spark_options["mainFileUri"] = resource["spark_file"]
            query_request["sparkOptions"] = spark_options

        if resource["additional_python_files"]:
            spark_options["pyFileUris"] = resource["additional_python_files"]
            query_request["sparkOptions"] = spark_options

        if resource["additional_files"]:
            spark_options["archiveUris"] = resource["additional_files"]
            query_request["sparkOptions"] = spark_options

        log.debug("Routine payload %s", query_request)

        return query_request

    def deploy_bucket(self, bucket_name):
        try:
            log.info(f"creating storage bucket {bucket_name}")
            VersionedClients().storage_buckets.execute(
                "insert",
                params={
                    "project": get_default_project(),
                    "body": {
                        "name": bucket_name,
                    },
                },
            )
            log.info(f"bucket {bucket_name} created")
        except HttpError as e:
            if e.resp.status == 409:
                log.info(f"storage bucket {bucket_name} already exists")

    def upload_file(self, file, bucket_name):
        log.debug(f"gs://{bucket_name}/{file}")
        VersionedClients().storage_objects.execute(
            "insert",
            params={
                "bucket": bucket_name,
                "uploadType": "media",
                "media_body": file,
                "body": {
                    "name": file,
                },
            },
        )
        log.info(f"uploaded file {file} to bucket {bucket_name}")
        return f"gs://{bucket_name}/{file}"

    def destroy_bucket(self, bucket_name):
        # Empty bucket
        log.info(f"emptying storage bucket {bucket_name}")
        objects = VersionedClients().storage_objects.execute(
            "list",
            params={
                "bucket": bucket_name,
            },
        )["items"]
        for obj in objects:
            VersionedClients().storage_objects.execute(
                "delete",
                params={
                    "bucket": bucket_name,
                    "object": obj["name"],
                },
            )
        try:
            log.info(f"deleting storage bucket {bucket_name}")
            VersionedClients().storage_buckets.execute(
                "delete",
                params={
                    "bucket": bucket_name,
                },
            )
            log.info(f"bucket {bucket_name} deleted")
        except HttpError as e:
            if e.resp.status == 404:
                log.info(f"storage bucket {bucket_name} already deleted")

    @staticmethod
    def stringify_func(func):
        lines, _ = inspect.getsourcelines(func)
        if lines[0].startswith("def"):
            lines.pop(0)
        return "".join(map(str.lstrip, lines))
