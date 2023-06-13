from goblet import Goblet

app = Goblet(function_name="example_api_gateway_security_definitions", region="us-central-1")
# See for more details https://goblet.github.io/goblet/build/html/topics.html#authentication

# Only allow custom_service_account on this method, which is defined in config.json
@app.route("/method_security", security=[{"custom_service_account": []}])
def method_security():
    return

# Allow custom_service_account and firebase on this method. They are defined in config.json
@app.route("/method_security", security=[{"custom_service_account": []}, {"firebase": []}])
def method_security():
    return

# Allow all on this method
@app.route("/allow_all", security=[])
def allow_all():
    return