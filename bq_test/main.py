from goblet import Goblet, goblet_entrypoint
app = Goblet(function_name="bigqueryremote", config={"custom_files": {"include":[".goblet"]}})

def entry(request):
    return app(request)

@app.bqremotefunction(
    dataset_id="blogs2",
    resource_type="cloudfunction"
)
def bqremotefunctionTest(x : int, y : int) -> int:
    z = x + y
    print(f"{x} + {y} = {z}")
    return z
