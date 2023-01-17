from urllib import request
from goblet import Goblet, jsonify, Response, goblet_entrypoint
from goblet.infrastructures.alerts import MetricCondition,LogMatchCondition,CustomMetricCondition
import logging

app = Goblet(function_name="goblet_example", region="us-central-1")
app.log.setLevel(logging.INFO)  # configure goblet logger level
goblet_entrypoint(app)

from typing import List
from marshmallow import Schema, fields

# Example http trigger
@app.http()
def main(request):
    return jsonify(request.json)


# Example http trigger that contains header
@app.http(headers={"X-Github-Event"})
def main(request):
    return jsonify(request.json)


# Example http triggers that matches header
@app.http(headers={"X-Github-Event": "issue"})
def main(request):
    return jsonify(request.json)


# Path param
@app.route("/home/{test}")
def home(test):
    return jsonify(test)


# Example query args
@app.route("/home")
def query_args():
    request = app.current_request
    q = request.args.get("q")
    return jsonify(q)


# POST request
@app.route("/home", methods=["POST"])
def post():
    request = app.current_request
    return jsonify(request.json)


# Typed Path Param
@app.route("/home/{name}/{id}", methods=["GET"])
def namer(name: str, id: int):
    return f"{name}: {id}"


class Point(Schema):
    lat = fields.Int()
    lng = fields.Int()


# Custom schema types
@app.route("/points")
def points() -> List[Point]:
    point = Point().load({"lat": 0, "lng": 0})
    return [point]


# Custom Marshmallow Fields
from marshmallow_enum import EnumField
from enum import Enum


def enum_to_properties(self, field, **kwargs):
    """
    Add an OpenAPI extension for marshmallow_enum.EnumField instances
    """
    if isinstance(field, EnumField):
        return {"type": "string", "enum": [m.name for m in field.enum]}
    return {}


app.handlers["route"].marshmallow_attribute_function = enum_to_properties


class StopLight(Enum):
    green = 1
    yellow = 2
    red = 3


class TrafficStop(Schema):
    light_color = EnumField(StopLight)


@app.route("/traffic")
def traffic() -> TrafficStop:
    return TrafficStop().dump({"light_color": StopLight.green})


# Returns follow openapi spec
# definitions:
#   TrafficStop:
#     type: object
#     properties:
#       light_color:
#         type: string
#         enum:
#         - green
#         - yellow
#         - red

# Pydantic Typing
from pydantic import BaseModel


class NestedModel(BaseModel):
    text: str


class PydanticModel(BaseModel):
    id: int
    nested: NestedModel


# Request Body Typing
@app.route("/pydantic", request_body=PydanticModel)
def traffic() -> PydanticModel:
    return jsonify(PydanticModel().dict)


# Custom Backend
@app.route("/custom_backend", backend="https://www.CLOUDRUN_URL.com/home")
def custom_backend():
    return


# Method Security
@app.route("/method_security", security=[{"your_custom_auth_id": []}])
def method_security():
    return


# Custom responses and request_types
@app.route(
    "/custom",
    request_body={
        "application/json": {"schema": {"type": "array", "items": {"type": "string"}}}
    },
    responses={"400": {"description": "400"}},
)
def custom():
    request = app.current_request
    assert request.data["string1", "string2"]
    return


# Example response object
@app.route("/response")
def response():
    return Response(
        {"failed": 400}, headers={"Content-Type": "application/json"}, status_code=400
    )


# Scheduled job
@app.schedule("5 * * * *")
def scheduled_job():
    return jsonify("success")


# Scheduled job with custom headers, method, and body
@app.schedule(
    "5 * * * *",
    httpMethod="POST",
    headers={"X-Custom": "header"},
    body="BASE64 ENCODED STRING",
)
def scheduled_job():
    headers = app.current_request.headers
    body = app.current_request.body
    method = app.current_request.method
    return jsonify("success")


# Pubsub topic
@app.topic("test")
def topic(data):
    app.log.info(data)
    return


# Pubsub topic with matching message attributes
@app.topic("test", attributes={"key": "value"})
def pubsub_attributes(data):
    app.log.info(data)
    return


# create a pubsub subscription instead of pubsub triggered function
@app.topic("test", use_subscription=True)
def pubsub_subscription_use_subscription(data):
    return


# create a pubsub subscription instead of pubsub triggered function and add filter
@app.topic(
    "test",
    use_subscription=True,
    filter='attributes.name = "com" AND -attributes:"iana.org/language_tag"',
)
def pubsub_subscription_filter(data):
    return


# Example Storage trigger on the create/finalize event
@app.storage("BUCKET_NAME", "finalize")
def storage(event):
    app.log.info(event)
    return


# Example before request
@app.before_request()
def add_db(request):
    app.g.db = "db"
    return request


# Example after request
@app.after_request()
def add_header(response):
    response.headers["X-Custom"] = "custom header"
    return response


# Example eventarc pubsub topic
@app.eventarc(topic="test")
def pubsub(data):
    app.log.info("pubsub")
    return


# Example eventarc direct event
@app.eventarc(
    event_filters=[
        {"attribute": "type", "value": "google.cloud.storage.object.v1.finalized"},
        {"attribute": "bucket", "value": "BUCKET"},
    ],
    region="us-east1",
)
def bucket(data):
    app.log.info("bucket_post")
    return


# Example eventarc audit log
@app.eventarc(
    event_filters=[
        {"attribute": "type", "value": "google.cloud.audit.log.v1.written"},
        {"attribute": "methodName", "value": "storage.objects.get"},
        {"attribute": "serviceName", "value": "storage.googleapis.com"},
    ],
    region="us-central1",
)
def bucket_get(data):
    app.log.info("bucket_get")
    return


# Example Cloudrun Job with schedule
@app.job("job1", schedule="* * * * *")
def job1_task1(id):
    app.log.info(f"job...{id}")
    return "200"


# Example Cloudrun Job with additional task
@app.job("job1", task_id=1)
def job1_task2(id):
    app.log.info(f"different task for job...{id}")
    return "200"

# Example BQ Remote Function
# Called in BQ with the following sql `select math_example_multiply(x,y,z) from my_dataset_id.table``
@app.bqremotefunction(dataset_id="my_dataset_id")
def multiply(x: int, y: int, z: int) -> int:
    w = x * y * z
    return w

# Example Redis Instance
app.redis("redis-test")

# Example VPC Connector
app.vpcconnector("vpc-conn-test")

# Example Metric Alert for the cloudfunction metric execution_count with a threshold of 10
app.alert("metric",conditions=[MetricCondition("test", metric="cloudfunctions.googleapis.com/function/execution_count", value=10)])

# Example Log Match metric that will trigger an incendent off of any Error logs
app.alert("error",conditions=[LogMatchCondition("error", "severity>=ERROR")])

# Example Metric Alert that creates a custom metric for severe errors with http code in the 500's and creates an alert with a threshold of 10
app.alert("custom",conditions=[CustomMetricCondition("custom", metric_filter='severity=(ERROR OR CRITICAL OR ALERT OR EMERGENCY) httpRequest.status=(500 OR 501 OR 502 OR 503 OR 504)', value=10)])
