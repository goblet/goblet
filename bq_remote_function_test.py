import os
import random
import time

from goblet import Goblet, jsonify
from goblet.backends import CloudFunctionV1
from goblet.resources.bq_remote_function import BigQueryRemoteFunction
from goblet.resources.scheduler import Scheduler

os.environ["GCLOUD_LOCATION"]="us-central1"
app = Goblet(function_name="bqRemoteConnectionTest",config={"main_file":"main.py", "custom_files":{"exclude":["test.py", "goblet", "setup.py", "bq_remote_function_test.py"]}})

@app.bqremotefunction(
    dataset_id="blogs2",
    resource_type="cloudfunction"
)
def bqremotefunctionTest(x : int, y : int) -> int:
    z = x + y
    print(f"{x} + {y} = {z}")
    return z


# scheduler = Scheduler("goblet", backend=CloudRun(Goblet(backend="cloudrun")))

# bq = BigQueryRemoteFunction(name="bqremotefunction", backend=app, resources=app.handlers["bqremotefunction"].resources)
# bq = BigQueryRemoteFunction("test", backend=app, resources=app.handlers["bqremotefunction"].resources)
app.handlers["bqremotefunction"].deploy(config={"main_file":"main.py", "custom_files":{"exclude":["test.py", "goblet", "setup.py", "bq_remote_function_test.py"]}})


# app = Goblet(function_name="test_function_bqremote2")
# cloudfunction = CloudFunctionV1(app)
# cloudfunction.deploy()
# app = Goblet(function_name="test_function_bqremote")
# app.handlers[""]
#app.handlers.get("bqremotefunction").deploy()
# @app.bqremotefunction(
#     function_name = app.function_name,
#     dataset="blogs"
# )
# def bqremotefunctionTest2(x : str) -> str:
#     print("Test 2")





