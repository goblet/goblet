from goblet import Goblet, goblet_entrypoint
from goblet.resources.bq_remote_function import BigQueryRemoteFunction

app=Goblet(function_name="bqremotefunction", config={"custom_files":{"include":[".goblet/*"]}})
goblet_entrypoint(app)

@app.bqremotefunction(
    dataset_id="blogs2",
    resource_type="cloudfunction"
)
def bqremotefunctionTest(x : int, y : int) -> int:
    z = x + y
    print(f"{x} + {y} = {z}")
    return z
