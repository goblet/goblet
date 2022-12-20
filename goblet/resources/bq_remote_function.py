import logging
from typing import get_type_hints

from goblet.resources.handler import Handler
from goblet.client import (
    get_default_project
)

from googleapiclient.errors import HttpError

log = logging.getLogger("goblet.deployer")
log.setLevel(logging.INFO)

BIGQUERY_DATATYPES = {
    bool : "BOOL",
    str : "STRING",
    int : "NUMERIC"
}

class BigQueryRemoteFunction(Handler):
    """Cloud Big Query Remote Functions job which calls remote query functions endpoint
        https://cloud.google.com/bigquery/docs/reference/standard-sql/remote-functions
    """
    valid_backends = ["cloudfunction", "cloudfunctionv2", "cloudrun"]
    can_sync = True
    resource_type = "bqremotefunction"
    create_statement = ""

    def get_hints(self, func):
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

    def register_bqremotefunction(self, name, func, kwargs):
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
        '''
        :param request: JSON formatted str
            The request is sent from bigquery routine

            Example:
            {
                'requestId': '82c508b3-6520-4406-ad06-6425f28fa41b',
                'caller': '//bigquery.googleapis.com/projects/premise-data-platform-dev/jobs/bquxjob_2597aba9_1852ff4c871',
                'sessionUser': 'diego.diaz@premise.com',
                'userDefinedContext': {   'X-Goblet-Name': 'bqremotefunctionTest' },
                'calls': [[1, 'a'], [1, 'a']]
            }
        :return: string JSON formatted

            Example
            {
                'replies': [  ]
            }

            * Replies is a JSON formatted str

        '''
        user_defined_context = request.json["userDefinedContext"]

        func_name = user_defined_context["X-Goblet-Name"]
        if not func_name:
            raise ValueError("No X-Goblet-Name header found")

        cloud_method = self.resources[func_name]
        if not cloud_method:
            raise ValueError(f"Method {func_name} not found")
        bq_tuples = request["calls"]
        tuples_replies = []
        for tuple in bq_tuples:
            tuples_replies.append(cloud_method["func"](*tuple))
        reply = {"replies" : tuples_replies}
        return reply

    def _deploy(self, source=None, entrypoint=None, config={}):
        log.info("deploying bigquery remote function......")
        bq_query_connection = self.deploy_bigqueryconnection(f"{self.name}", {"cloudResource": {}})

        for resource_name, resource in self.resources.items():
            create_routine_query = self.create_routine_payload(resource, bq_query_connection)
            try:
                print(self.name)
                print(bq_query_connection["name"])
                print(bq_query_connection)
                self.versioned_clients.bigquery_routines.execute(
                    "insert", params={"body": create_routine_query, "projectId":get_default_project(), "datasetId":resource["dataset_id"]}, parent_key="projectId"
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
                "create", params={"body": remote_function, "connectionId":connection_id}
            )
            log.info(f"created bigquery connection name: {remote_function_name} for {self.name}")

        except HttpError as e:
            if e.resp.status == 409:
                client = self.versioned_clients.bigqueryconnectionget
                bq_connection = client.execute(
                    "get", params={"name": client.parent+connection_id}, parent=False
                )
                # log.info(f"creating cloud function invoker policy")
                # policy = self.create_policy(bq_connection)
                # self.versioned_clients.bigquery_iam.execute(
                #     "setIamPolicy", params={"body": policy,"resource":f"projects/98058317567/locations/us-central1/connections/bqremotefunctionTest"}, parent=False)
                # log.info(f"updated bigquery connection job: {remote_function_name} for {self.name}")
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
