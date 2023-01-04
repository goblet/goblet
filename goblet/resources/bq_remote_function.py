import json
import logging
from typing import get_type_hints

from goblet.resources.handler import Handler
from goblet.client import (
    get_default_project, get_default_location
)

from googleapiclient.errors import HttpError

log = logging.getLogger("goblet.deployer")
log.setLevel(logging.INFO)

'''
    Allowed types for BigQuery remote functions
    https://cloud.google.com/bigquery/docs/reference/standard-sql/remote-functions#limitations
'''
BIGQUERY_DATATYPES = {
    bool : "BOOL",
    str : "STRING",
    int : "INT64",
    float: "FLOAT64",
    list: "JSON",
    dict: "JSON"
}

class BigQueryRemoteFunction(Handler):
    """
        Cloud Big Query Remote Functions (Big Query routines) connected to cloudfunctions or
        cloudrun
        https://cloud.google.com/bigquery/docs/reference/standard-sql/remote-functions
    """

    valid_backends = ["cloudfunction", "cloudfunctionv2", "cloudrun"]
    can_sync = True
    resource_type = "bqremotefunction"

    def register_bqremotefunction(self, name, func, kwargs):
        """
        Register in handler resources
        :param name: name of resource
        :param func: function/method
        :param kwargs:
        :return:
        """
        kwargs = kwargs.pop("kwargs")
        headers = kwargs.get("headers", {})
        input, output = self.get_hints(func)
        self.resources[name] = {
            "routine_name": name,
            "dataset_id": kwargs["dataset_id"],
            "inputs": input,
            "output" : output,
            "func": func
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
            print(f"error cloud method {cloud_method}")
            raise ValueError(f"Method {func_name} not found")
        print(f'obtaining calls {request.json["calls"]}')
        bq_tuples = request.json["calls"]
        tuples_replies = []
        for tuple in bq_tuples:
            tuples_replies.append(cloud_method["func"](*tuple))
        reply = {"replies" : tuples_replies}
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
        log.info("Deploying bigquery remote functions")
        bq_query_connection = None
        try:
            bq_query_connection = self.deploy_bigquery_connection(f"{self.name}")
            self.backend.set_iam_policy(self.versioned_clients.cloudfunctions,
                f"projects/{get_default_project()}/locations/{get_default_location()}/functions/{self.name}",
                bq_query_connection['cloudResource']['serviceAccountId'])
        except HttpError as e:
            if e.resp.status == 409:
                log.info(f"Connection already created.bigquery query: for {self.name}")
                pass
            else:
                log.error(f"Updated bigquery query: for {e.error_details}")
                raise e

        for resource_name, resource in self.resources.items():
            create_routine_query = self.create_routine_payload(resource, bq_query_connection)
            routine_name = resource["routine_name"]
            try:
                self.versioned_clients.bigquery_routines.execute(
                    "insert", params={"body": create_routine_query, "projectId":get_default_project(),
                                      "datasetId":resource["dataset_id"]}, parent_key="projectId"
                )
                log.info(f"Created bq routine {routine_name}")
            except HttpError as e:
                if e.resp.status == 409:
                    log.info(f"Remote function already exist, updating for name: {routine_name}")
                    self.versioned_clients.bigquery_routines.execute(
                        "update", params={"body": create_routine_query, "projectId": get_default_project(),
                                          "datasetId": resource["dataset_id"], "routineId":routine_name}, parent_key="projectId"
                    )
                else:
                    log.error(f"Bigquery remote function couldn't be created nor updated"
                              f"name {routine_name} with error: {e.error_details}")
                    raise e

    def _sync(self, dryrun=False):
        if len(self.resources) <= 0:
            return
        resource = list(self.resources.values())[0]
        print(resource)
        # bq_connection = client.execute(
        #     "get", params={"name": client.parent + "/connections/" + connection_id}, parent=False
        # )

        # routines = self.versioned_clients.bigquery_routines.execute("list", params={"projectId":get_default_project(),
        #                                                                             "datasetId":})
        # jobs = self.versioned_clients.cloudscheduler.execute("list").get("jobs", [])
        # filtered_jobs = list(
        #     filter(lambda job: f"jobs/{self.name}-" in job["name"], jobs)
        # )
        # for filtered_job in filtered_jobs:
        #     split_name = filtered_job["name"].split("/")[-1].split("-")
        #     filtered_name = split_name[1]
        #     if not self.resources.get(filtered_name):
        #         log.info(f'Detected unused job in GCP {filtered_job["name"]}')
        #         if not dryrun:
        #             # TODO: Handle deleting multiple jobs with same name
        #             self._destroy_job(filtered_name)

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
                "create", params={"body": resource_type, "connectionId":connection_id}
            )
            log.info(f"Created bigquery connection name: {connection_id}")

        except HttpError as e:
            if e.resp.status == 409:
                log.info(f"Bigquery connection already exist with name: {connection_name} for {self.name}")
                client = self.versioned_clients.bigquery_connections
                bq_connection = client.execute(
                    "get", params={"name": client.parent+"/connections/"+connection_id}, parent=False
                )
                pass
            else:
                raise e
        return bq_connection

    def destroy(self):
        """
        Destroy connection then destroy one by one every routine
        :return:
        """
        if not self.resources:
            return
        self._destroy_bigquery_connection()
        for resource_name, resource in self.resources.items():
            self._destroy_resource(resource_name)

    def _destroy_bigquery_connection(self):
        """
        Destroy bigquery connection, if already exist do nothing
        :return:
        """
        connection_id = f"{self.name}"
        client = self.versioned_clients.bigquery_connections
        try:
            client.execute("delete", params={"name": client.parent +"/connections/"+ connection_id}, parent=False)
        except HttpError as e:
            if e.resp.status == 404:
                log.info("Connection already destroyed")
            else:
                raise e
        return True

    def _destroy_resource(self, resource_name):
        try:
            resource = self.resources[resource_name]
            dataset_id = resource["dataset_id"]
            routine_id = resource["routine_name"]
            self.versioned_clients.bigquery_routines.execute(
                "delete",
                params={"projectId":get_default_project(),"datasetId":dataset_id,"routineId":routine_id},parent=False
            )
            log.info(f"Destroyed routine {routine_id} for dataset {dataset_id}")
        except HttpError as e:
            if e.resp.status == 404:
                log.info("Routine already destroyed")
            else:
                raise e

    def get_hints(self, func):
        """
        Inspect hint in function func and creates an array for input and output with SQL Datatypes
        according to https://cloud.google.com/bigquery/docs/reference/standard-sql/data-types
        restricted to https://cloud.google.com/bigquery/docs/reference/standard-sql/remote-functions#limitations
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
                inputs.append({"name":var_name, "data_type": BIGQUERY_DATATYPES[var_type]})
        return inputs, outputs

    def create_routine_payload(self, resource, connection):
        """
        Create a routine object according to BigQuery specification
        :param resource: a resource saved in resources in Handler
        :param connection: a dict representing a bigquery connection
                (https://cloud.google.com/bigquery/docs/reference/bigqueryconnection/rest/v1/projects.locations.connections)
        :return: a dict representing a routine according to
                https://cloud.google.com/bigquery/docs/reference/rest/v2/routines
        """
        remote_function_options = {
                "endpoint": self.backend.http_endpoint,
                "connection": connection["name"],
                "userDefinedContext": {
                    "X-Goblet-Name": resource['routine_name']
                }
            }
        routine_reference = {
                "projectId": get_default_project(),
                "datasetId": resource["dataset_id"],
                "routineId": resource["routine_name"]
            }

        arguments = []
        for input in resource["inputs"]:
            argument = {"name":input["name"],
             "dataType":{
                 "typeKind":input["data_type"]
                }
             }
            arguments.append(argument)
        return_type = {"typeKind": resource["output"][0]}
        language = "SQL"

        query_request = {
            "language":language,
            "routineReference": routine_reference,
            "routineType": "SCALAR_FUNCTION",
            "arguments":arguments,
            "returnType": return_type,
            "remoteFunctionOptions":remote_function_options
        }

        return query_request


