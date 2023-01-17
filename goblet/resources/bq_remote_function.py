import json
import logging
from typing import get_type_hints

from googleapiclient.errors import HttpError

from goblet.resources.handler import Handler
from goblet.client import get_default_project


log = logging.getLogger("goblet.deployer")
log.setLevel(logging.INFO)

BIGQUERY_DATATYPES = {
    bool: "BOOL",
    str: "STRING",
    int: "INT64",
    float: "FLOAT64",
    list: "JSON",
    dict: "JSON",
}


class BigQueryRemoteFunction(Handler):
    """
    Cloud Big Query Remote Functions (Big Query routines) connected to cloudfunctions or
    cloudrun
    https://cloud.google.com/bigquery/docs/reference/standard-sql/remote-functions

    Allowed types for BigQuery remote functions
    https://cloud.google.com/bigquery/docs/reference/standard-sql/remote-functions#limitations

    """

    valid_backends = ["cloudfunction", "cloudfunctionv2", "cloudrun"]
    can_sync = False
    resource_type = "bqremotefunction"

    def register(self, name, func, kwargs):
        """
        Register in handler resources
        :param name: name of resource
        :param func: function/method
        :param kwargs:
        :return:
        """
        kwargs = kwargs.pop("kwargs")
        _input, _output = BigQueryRemoteFunction._get_hints(func)
        # Routine names must contain only letters, numbers, and underscores, and be at most 256 characters long.
        routine_name = self.name + "_" + name
        routine_name = routine_name.replace("-", "_")
        self.resources[routine_name] = {
            "routine_name": routine_name,
            "dataset_id": kwargs["dataset_id"],
            "inputs": _input,
            "output": _output,
            "func": func,
        }
        return True

    def __call__(self, request, context=None):
        """
        To be called from BigQuery routines
        :param request: <Request class>
                        Must contain X-Goblet-Name equals registered
                        name for cloudfunction as key on userDefinedContext

        :param context:
        :return: str Json repr
        """
        user_defined_context = request.json["userDefinedContext"]
        func_name = user_defined_context["X-Goblet-Name"]
        if not func_name:
            raise ValueError("No X-Goblet-Name header found")

        cloud_method = self.resources[func_name]
        if not cloud_method:
            raise ValueError(f"Method {func_name} not found")
        bq_tuples = request.json["calls"]
        tuples_replies = []
        for _tuple in bq_tuples:
            tuples_replies.append(cloud_method["func"](*_tuple))
        reply = {"replies": tuples_replies}
        return json.dumps(reply)

    def _deploy(self, source=None, entrypoint=None, config={}):
        """
        Get a connection resource for Handler.name and set cloudfunction
        invoker IAM role to the service account assigned to the connection
        for all the cloudfunctions registered in this Handler
        :param source: inherited from Handler
        :param entrypoint: inherited from Handler
        :param config: inherited from Handler
        :return:
        """
        if not self.resources:
            return
        log.info("Deploying bigquery remote functions")
        bq_query_connection = None
        try:
            bq_query_connection = self.deploy_bigquery_connection(f"{self.name}")
            self.backend.set_iam_policy(
                bq_query_connection["cloudResource"]["serviceAccountId"]
            )
        except HttpError as exception:
            if exception.resp.status == 409:
                log.info("Connection already created bigquery query: for %s", self.name)
            else:
                log.error("Create connection %s", exception.error_details)
                raise exception

        for _, resource in self.resources.items():
            create_routine_query = self.create_routine_payload(
                resource, bq_query_connection
            )
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
                    log.info("Updated remote function %s", routine_name)
                else:
                    log.error(
                        "Bigquery remote function couldn't be created "
                        "nor updated name %s with error: %s",
                        routine_name,
                        exception.error_details,
                    )
                    raise exception

        # def _sync(self, dryrun=False):

        # ITERATE ALL DATASET TO GET ALL ROUTINES
        # :param dryrun:
        # :return:

        # client = self.versioned_clients.bigquery_routines
        # checked_dataset_id = []
        # for routine_id, routine in self.resources.items():
        #     dataset_id = routine["dataset_id"]
        #     if dataset_id in checked_dataset_id:
        #         continue
        #     checked_dataset_id.append(dataset_id)
        #     available_routines = client.execute("list",
        #     params={"datasetId": dataset_id, "projectId": get_default_project()},
        #     parent=False)
        #     if "routines" not in available_routines:
        #         continue
        #     for available_routine in available_routines["routines"]:
        #         if available_routine["routineReference"]["routineId"] not in self.resources:
        #               log.info(f'Detected unused routine in GCP
        #                {available_routine["routineReference"]["routineId"]}')
        #         if not dryrun:
        #         self.destroy_routine(dataset_id,
        #         available_routine["routineReference"]["routineId"])

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

    def deploy_bigquery_connection(self, connection_name):
        """
            Creates (or get if exists) a connection resource with Handler.name
        :param connection_name: name for the connection
        :return:
        """
        connection_id = f"{self.name}"
        resource_type = {"cloudResource": {}}
        try:
            bq_connection = self.versioned_clients.bigquery_connections.execute(
                "create", params={"body": resource_type, "connectionId": connection_id}
            )
            log.info(f"Created bigquery connection name: {connection_id}")

        except HttpError as exception:
            if exception.resp.status == 409:
                log.info(
                    f"Bigquery connection already exist with name: {connection_name} for {self.name}"
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
        log.info(bq_connection)
        return bq_connection

    def destroy_bigquery_connection(self):
        """
        Destroy bigquery connection, if already exist do nothing
        :return:
        """
        connection_id = f"{self.name}"
        client = self.versioned_clients.bigquery_connections
        try:
            client.execute(
                "delete",
                params={"name": client.parent + "/connections/" + connection_id},
                parent=False,
            )
        except HttpError as exception:
            if exception.resp.status == 404:
                log.info(f"Connection {connection_id} already destroyed")
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

    def _get_hints(func):
        """
        Inspect hint in function func and creates an array for input and output with SQL Datatypes
        according to https://cloud.google.com/bigquery/docs/reference/standard-sql/data-types
        restricted to
        https://cloud.google.com/bigquery/docs/reference/standard-sql/remote-functions#limitations
        :param func: function/method class to be inspected
        :return: inputs, outputs
                inputs = [{"name":<variable_name>, "data_type":<data_type>}]
                See data types on BIGQUERY_DATATYPES
        """
        type_hints = get_type_hints(func)
        inputs = []
        outputs = []

        for var_name, var_type in type_hints.items():
            if var_name == "return":
                outputs.append(BIGQUERY_DATATYPES[var_type])
            else:
                inputs.append(
                    {"name": var_name, "data_type": BIGQUERY_DATATYPES[var_type]}
                )
        return inputs, outputs

    def create_routine_payload(self, resource, connection):
        """
        Create a routine object according to BigQuery specification
        :param resource: a resource saved in resources in Handler
        :param connection: a dict representing a bigquery connection
        (https://cloud.google.com/bigquery/docs/reference/bigqueryconnection/
            rest/v1/projects.locations.connections)
        :return: a dict representing a routine according to
                https://cloud.google.com/bigquery/docs/reference/rest/v2/routines
        """
        remote_function_options = {
            "endpoint": self.backend.http_endpoint,
            "connection": connection["name"],
            "userDefinedContext": {"X-Goblet-Name": resource["routine_name"]},
        }
        routine_reference = {
            "projectId": get_default_project(),
            "datasetId": resource["dataset_id"],
            "routineId": resource["routine_name"],
        }

        arguments = []
        for _input in resource["inputs"]:
            argument = {
                "name": _input["name"],
                "dataType": {"typeKind": _input["data_type"]},
            }
            arguments.append(argument)
        return_type = {"typeKind": resource["output"][0]}
        language = "SQL"

        query_request = {
            "language": language,
            "routineReference": routine_reference,
            "routineType": "SCALAR_FUNCTION",
            "arguments": arguments,
            "returnType": return_type,
            "remoteFunctionOptions": remote_function_options,
        }

        return query_request
