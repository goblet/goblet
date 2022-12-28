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

BIGQUERY_DATATYPES = {
    bool : "BOOL",
    str : "STRING",
    int : "INT64",
    float: "NUMERIC",
    list: "JSON",
    dict: "JSON"
}

class BigQueryRemoteFunction(Handler):
    """Cloud Big Query Remote Functions (Big Query routines) connected to cloudfunctions or
    cloudrun
        https://cloud.google.com/bigquery/docs/reference/standard-sql/remote-functions
    """
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
        log.info("Deploying bigquery remote functions")
        bq_query_connection = None
        try:
            bq_query_connection = self.deploy_bigqueryconnection(f"{self.name}")
            self.backend.set_iam_policy(
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
            routine_name = resource["name"]
            try:
                self.versioned_clients.bigquery_routines.execute(
                    "insert", params={"body": create_routine_query, "projectId":get_default_project(),
                                      "datasetId":resource["dataset_id"]}, parent_key="projectId"
                )
                log.info(f"Created bq routine {routine_name}")
            except HttpError as e:
                if e.resp.status == 409:
                    log.info(f"Bigquery remote function already exist name: {routine_name}")
                    pass
                else:
                    log.error(f"Bigquery remote function couldn't be created "
                              f"name {routine_name} with error: {e.error_details}")
                    raise e

    def _sync(self, dryrun=False):
        jobs = self.versioned_clients.cloudscheduler.execute("list").get("jobs", [])
        filtered_jobs = list(
            filter(lambda job: f"jobs/{self.name}-" in job["name"], jobs)
        )
        for filtered_job in filtered_jobs:
            split_name = filtered_job["name"].split("/")[-1].split("-")
            filtered_name = split_name[1]
            if not self.resources.get(filtered_name):
                log.info(f'Detected unused job in GCP {filtered_job["name"]}')
                if not dryrun:
                    # TODO: Handle deleting multiple jobs with same name
                    self._destroy_job(filtered_name)

    def deploy_bigqueryconnection(self, remote_function_name):
        connection_id = f"{self.name}"
        resource_type = {"cloudResource": {}}
        try:
            bq_connection = self.versioned_clients.bigqueryconnection.execute(
                "create", params={"body": resource_type, "connectionId":connection_id}
            )
            log.info(f"Created bigquery connection name: {connection_id}")

        except HttpError as e:
            if e.resp.status == 409:
                log.info(f"Bigquery connection already exist with name: {remote_function_name} for {self.name}")
                client = self.versioned_clients.bigqueryconnectionget
                bq_connection = client.execute(
                    "get", params={"name": client.parent+connection_id}, parent=False
                )
                pass
            else:
                raise e
        try:
            log.info(f"Creating cloud function invoker policy")
            policy = self.create_policy(bq_connection)
            self.versioned_clients.cloudfunctions.execute(
                "setIamPolicy", params={"body": policy}, parent_key="resource",
                parent_schema=f"projects/premise-data-platform-dev/locations/us-central1/functions/bqremotefunctionTest2")
            log.info(f"updated bigquery connection job: {remote_function_name} for {self.name}")
        except:
            log.error("Couldnt assign invoker policy for bigquery remote connection")

        return bq_connection

    def destroy(self):
        if not self.resources:
            return
        for job_name in self.resources.keys():
            self._destroy_bqremote(job_name)

    def _destroy_bqremote(self, job_name):
        try:
            self.versioned_clients.bigquery.execute(
                "delete",
                parent_schema="{project_id}/locations/{location_id}/jobs/"
                + self.name
            )
            log.info(f"Destroying scheduled job {job_name}......")
        except HttpError as e:
            if e.resp.status == 404:
                log.info("Scheduled jobs already destroyed")
            else:
                raise e

    def create_policy(self, connection):
        policy = {
            "policy": {
                "bindings":{
                    "role": "roles/cloudfunctions.invoker",
                    "members": [
                        f"serviceAccount:{connection['cloudResource']['serviceAccountId']}"
                    ]
                }
            }
        }
        return policy

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
