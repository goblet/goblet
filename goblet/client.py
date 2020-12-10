import pickle
import os.path
import time 

from googleapiclient.discovery import build

import google.auth


def get_default_project():
    for k in ('GOOGLE_PROJECT', 'GCLOUD_PROJECT',
              'GOOGLE_CLOUD_PROJECT', 'CLOUDSDK_CORE_PROJECT'):
        if k in os.environ:
            return os.environ[k]

    return None

def get_default_location():
    for k in ('GOOGLE_ZONE', 'GCLOUD_ZONE', 'CLOUDSDK_COMPUTE_ZONE',
              'GOOGLE_REGION', 'GCLOUD_REGION', 'CLOUDSDK_COMPUTE_REGION',
              'GOOGLE_LOCATION', 'GCLOUD_LOCATION'):
        if k in os.environ:
            return os.environ[k]

    return None

def get_credentials():
    """get user credentials and save them for future use
    """
    credentials, project = google.auth.default()
    return credentials

class Client:
    def __init__(self, resource,version='v1', credentials=None, calls=None, parent_schema=None):
        self.project_id = get_default_project()
        self.location_id = get_default_location()
        self.calls = calls
        self.resource = resource
        self.version = version
        self.parent_schema = parent_schema
        self.credentials = credentials or get_credentials()

        self.client = build(resource, version, credentials=self.credentials, cache_discovery=False)
        
        self.parent = None
        if self.parent_schema:
            self.parent = self.parent_schema.format(project_id=self.project_id, location_id=self.location_id)

    def __call__(self):
        return self.client 

    def wait_for_operation(self, operation, timeout=600):
        done = False
        operation_client = Client(
            self.resource, 
            version=self.version, 
            credentials=self.credentials, 
            calls="projects.locations.operations",
            parent_schema= operation
        )
        count = 0
        sleep_duration = 4
        while not done or count > timeout:
            resp = operation_client.execute('get', parent_key="name")
            done = resp.get("done")
            time.sleep(sleep_duration)
            count += sleep_duration

    def execute(self, api, calls=None, parent_schema=None, parent=True, parent_key='parent', params=None):
        api_chain = self.client
        _params = params or {}
        _calls = calls or self.calls
        if parent_schema:
            parent_schema = parent_schema.format(project_id=self.project_id, location_id=self.location_id)
        _schema = parent_schema or self.parent
        
        if isinstance(_calls, str):
            calls = _calls.split('.')
        for call in calls:
            api_chain = getattr(api_chain, call)()

        if _schema and parent:
            _params[parent_key] = _schema
        return getattr(api_chain, api)(**_params).execute()
