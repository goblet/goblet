import re
from os.path import join, dirname

DATA_DIR = join(dirname(__file__), "tests", "data", "http")
PROJECT_ID = "goblet"
DATA_DIR_MAIN = join(dirname(__file__), "tests", "data")


def sanitize_project_name(dirty_str):
    sanitized = "projects/{}/".format(PROJECT_ID)
    return re.sub(r"projects/([0-9a-zA-Z_-]+)/", sanitized, dirty_str)


def dummy_function():
    return None


def mock_dummy_function(mock):
    def dummy_function(event=None):
        return mock()

    return dummy_function
