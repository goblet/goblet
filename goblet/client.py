import pickle
import os.path
from googleapiclient.discovery import build
# from google_auth_oauthlib.flow import InstalledAppFlow
# from google.auth.transport.requests import Request
# from google.oauth2 import service_account
import google.auth


# If modifying these scopes, delete the file token.pickle.
# SCOPES = ['https://www.googleapis.com/auth/documents.readonly']
CLOUD_SCOPES = frozenset(['https://www.googleapis.com/auth/cloud-platform'])


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

# def function_api():
#     cloudfunctions = Client("cloudfunctions", 'v1',calls='projects.locations.functions', parent_schema='projects/{project_id}/locations/{location_id}')
#     x = cloudfunctions.execute('list')
#     return x 
# function_api =

class Client:
    def __init__(self, resource,version='v1', credentials=None, calls=None, parent_schema=None):
        self.project_id = get_default_project()
        self.location_id = get_default_location()
        self.calls = calls
        self.credentials = credentials or get_credentials()

        self.client = build(resource, version, credentials=self.credentials, cache_discovery=False)
        self.parent_schema = parent_schema
        if self.parent_schema:
            self.parent = self.parent_schema.format(project_id=self.project_id, location_id=self.location_id)

    def __call__(self):
        return self.client 

    def execute(self, api, parent=True, parent_key='parent', params=None):
        api_chain = self.client
        params = params or {}

        if isinstance(self.calls, str):
            calls = self.calls.split('.')
        for call in calls:
            api_chain = getattr(api_chain, call)()

        if self.parent_schema and parent:
            params[parent_key] = self.parent
        return getattr(api_chain, api)(**params).execute()
