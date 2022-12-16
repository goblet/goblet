import logging
from typing import get_type_hints


from goblet.backends import CloudFunctionV1, CloudRun
from goblet.resources.handler import Handler
from goblet.client import (
    get_default_project,
    get_default_location,
)
from goblet.common_cloud_actions import get_cloudrun_url, get_cloudfunction_url
from goblet.config import GConfig

from googleapiclient.errors import HttpError

log = logging.getLogger("goblet.deployer")
log.setLevel(logging.INFO)

BIGQUERY_DATATYPES = {
    bool : "Boolean",
    str : "String",
    int : "NUMERIC"
}

class BigQueryRemoteFunction(Handler):
    """Cloud Big Query Remote Functions job which calls remote query functions endpoint
        https://cloud.google.com/bigquery/docs/reference/standard-sql/remote-functions
    """
    valid_backends = ["cloudfunction", "cloudfunctionv2", "cloudrun"]
    can_sync = True
    resource_type = "bq_remote_function"
    create_statement = ""

    def get_hints(self, func):
        type_hints = get_type_hints(func)
        inputs = []
        outputs = []

        for var_name, var_type in type_hints.items():
            if var_name == "return":
                outputs.append(BIGQUERY_DATATYPES[var_type])
            else:
                inputs.append(f"{var_name} {BIGQUERY_DATATYPES[var_type]}")
        return inputs, outputs

    def create_routine_payload(self, resource, connection):
        remote_function_options = {
                "endpoint": self.backend.http_endpoint,
                "connection": connection["name"],
                "userDefinedContext": {
                    "X_GOBLET_NAME": resource['routine_name']
                }
            }
        routine_reference = {
                "projectId": get_default_project(),
                "datasetId": resource["dataset_id"],
                "routineId": resource["routine_name"]
            }
        return_type = {"typeKind": "INT64"}
        arguments = [
            {"name":"X",
             "dataType":{
                 "typeKind":"INT64"
                }
             },
            {"name": "Y",
             "dataType": {
                 "typeKind": "INT64"
                }
             }
        ]

        query_request = {
            "routineReference": routine_reference,
            "routineType": "SCALAR_FUNCTION",
            "arguments":arguments,
            "returnType": return_type,
            "remoteFunctionOptions":remote_function_options
        }

        return query_request

    def create_routine(self, resource, connection):
        signature = f"{resource['routine_name']}({', '.join(resource['inputs'])}) RETURNS {','.join(resource['outputs'])}"
        project_id = get_default_project()
        connection_name = self.name
        location = get_default_location()
        # create_statement = f"CREATE FUNCTION `{project_id}.{resource['dataset_id']}`.{signature} REMOTE WITH " \
        #                    f"CONNECTION " \
        #                    f"`{project_id}.{location}.{connection_name}` " \
        #                    f"OPTIONS(" \
        #                    f"endpoint=`{self.backend.http_endpoint}`, " \
        #                    f"user_defined_context=[(\"X_GOBLET_NAME\",\"{resource['routine_name']}\")]" \
        #                    f")"
        create_statement = "CREATE FUNCTION blogs2.bqremotefunctionTest(x NUMERIC, y NUMERIC) RETURNS NUMERIC " \
                           "REMOTE WITH CONNECTION bqRemoteConnectionTest " \
                           "OPTIONS(endpoint='https://us-central1-premise-data-platform-dev.cloudfunctions.net/bqRemoteConnectionTest')"
        create_statement = "CREATE TEMP FUNCTION addFourAndDivideAny(x ANY TYPE, y ANY TYPE) AS ( (x + 4) / y )"
        # create_statement = f"SELECT * FROM [{resource['dataset_id']}.users]"
        print(create_statement)
        return create_statement

    def register_bqremotefunction(self, name, func, kwargs):
        kwargs = kwargs.pop("kwargs")
        headers = kwargs.get("headers", {})
        input, output = self.get_hints(func)
        self.resources[name] = {
            "routine_name": name,
            "dataset_id": kwargs["dataset_id"],
            "inputs": input,
            "outputs" : output
        }
        return True

    def __call__(self, request, context=None):
        headers = request.headers
        func_name = headers.get("X-Goblet-Name")
        if not func_name:
            raise ValueError("No X-Goblet-Name header found")

        cloud_method = self.resources[func_name]
        if not cloud_method:
            raise ValueError(f"Method {func_name} not found")
        return cloud_method["func"]()

    def _deploy(self, source=None, entrypoint=None, config={}):
        log.info("deploying bigquery remote function......")
        bq_query_connection = self.deploy_bigqueryconnection(f"{self.name}", {"cloudResource": {}})

        for resource_name, resource in self.resources.items():
            # create_routine_query = self.create_routine(resource, bq_query_connection)
            create_routine_query = self.create_routine_payload(resource, bq_query_connection)
            try:
                # query_request = {"query": create_routine_query}

                self.versioned_clients.bigqueryconnection.execute(
                    "insert", params={"body": create_routine_query, "connectionId": bq_query_connection.name}
                )
                log.info(f"created bq routine.")
            except HttpError as e:
                if e.resp.status == 409:
                    log.info(f"updated bigquery query: for {self.name}")
                    pass
                else:
                    log.error(f"updated bigquery query: for {e.error_details}")
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

    def deploy_bigqueryconnection(self, remote_function_name, remote_function):
        connection_id = f"{self.name}"

        try:

            bq_connection = self.versioned_clients.bigqueryconnection.execute(
                "create", params={"body": remote_function, "connectionId":self.name}
            )
            log.info(f"created bigquery connection name: {remote_function_name} for {self.name}")

        except HttpError as e:
            if e.resp.status == 409:
                client = self.versioned_clients.bigqueryconnectionget
                bq_connection = client.execute(
                    "get", params={"name": client.parent+connection_id}, parent=False
                )
                log.info(f"creating cloud function invoker policy")
                policy = self.create_policy(bq_connection)
                self.versioned_clients.bigquery_iam.execute(
                    "setIamPolicy", params={"body": policy,"resource":f"projects/98058317567/locations/us-central1/connections/bqremotefunctionTest"}, parent=False)
                log.info(f"updated bigquery connection job: {remote_function_name} for {self.name}")
                pass
            else:
                raise e

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
                    "role": "roles/cloudfunctions.developer",
                    "members": [
                        f"serviceAccount:{connection['cloudResource']['serviceAccountId']}"
                    ]
                }
            }
        }
        return policy
