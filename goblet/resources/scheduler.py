from collections import OrderedDict 
from ruamel import yaml
import base64
import json 
import logging
import time 
import re

from goblet.handler import Handler
from goblet.client import Client, get_default_project
from googleapiclient.errors import HttpError

log = logging.getLogger('goblet.deployer')
log.setLevel(logging.INFO)

class Scheduler(Handler):
    def __init__(self, name, routes={}):
        self.cloudfunction = f"projects/{get_default_project()}/locations/{get_default_location()}/functions/{self.name}"
        self.jobs = jobs
        self.api_client = self._create_api_client()

        def _create_api_client(self):
            return Client("cloudscheduler", 'v1',calls='projects.locations.jobs', parent_schema='projects/{project_id}/locations/{location_id}')

        def register_job(self, name, func, kwargs):
            schedule = kwargs["schedule"]
            timezone = kwargs.get("timezone", "utc")
            description = kwargs.get("description", "Created by goblet")
            self.jobs[name] = {
                "job_json": {
                    "name": name,
                    "schedule": schedule,
                    "timeZone": timezone,
                    "description": description,
                    "HttpTarget": {
                        "uri": self.cloudfunction,
                        "headers": {
                            'X-Goblet-Type':'schedule',
                            'X-Goblet-Name': name
                        },
                        "httpMethod": "GET"
                    }
                },
                "func":func
            }

        def __call__(self, request, context=None):
            headers = request.headers
            func_name = headers.get("X-Goblet-Name")
            if not func_name:
                raise ValueError(f"No X-Goblet-Name header found")

            job = self.jobs[func_name]
            if not job:
                raise ValueError(f"Function {func_name} not found")
            return job["func"]()

        def deploy(self):
            for job in self.jobs.values():
                self.deploy_job(job["job_json"])

        def deploy_job(self, job):
            try:
                resp = self.api_client.execute('create', params={'body':job})
                self.api_client.wait_for_operation(resp["name"])
            except HttpError as e:
                if e.resp.status == 409:
                    # TODO
                    log.info(f"should update...")
                else:
                    raise e


        def destroy(self):
            for job_name in self.jobs():
                self._destroy_job(job_name)
        
        def _destroy_job(job_name):
        try: 
            scheduler_client = Client("cloudscheduler", 'v1',calls='projects.locations.jobs',parent_schema='projects/{project_id}/locations/{location_id}/jobs/' + self.job_name)
            scheduler_client.execute('delete',parent_key="name")
            log.info("destroying scheduled function......")
        except HttpError as e:
            if e.resp.status == 404:
                log.info(f"scheduled function already destroyed")
            else:
                raise e