from goblet import Goblet, jsonify, Response
import logging 

app = Goblet(function_name="goblet_example",region='us-central-1', local="test")
app.log.setLevel(logging.INFO) # configure goblet logger level

from typing import List
from marshmallow import Schema, fields

# Example http trigger
@app.http()
def main(request):
    return jsonify(request.json)

# path param
@app.route('/home/{test}')
def home(test):
    return jsonify(test)
    
# example query args
@app.route('/home')
def query_args():
    request = app.current_request
    q = request.args.get("q")
    return jsonify(q)

# POST request
@app.route('/home', methods=["POST"])
def post():
    request = app.current_request
    return jsonify(request.json)

# Typed Path Param
@app.route('/home/{name}/{id}', methods=["GET"])
def namer(name: str, id: int):
    return f"{name}: {id}"

class Point(Schema):
    lat = fields.Int()
    lng = fields.Int()

# custom schema types
@app.route('/points')
def points() -> List[Point]:
    point = Point().load({"lat":0, "lng":0})
    return [point]

# custom responses and request_types
@app.route('/custom', request_body={'application/json': {'schema': {"type": "array", "items": {'type': 'string'}}}},
responses={'400': {'description': '400'}})
def custom():
    request = app.current_request
    assert request.data ["string1", "string2"]
    return

# example response object
@app.route('/response')
def response():
    return Response({"failed":400},headers={"Content-Type":"application/json"}, status_code=400)

# scheduled job
@app.schedule('5 * * * *')
def scheduled_job():
    return jsonify("success")

# pubsub topic
@app.topic('test')
def topic(data):
    app.log.info(data)
    return 

# pubsub topic with matching message attributes
@app.topic('test', attributes={'key': 'value'})
def home2(data):
    app.log.info(data)
    return 

# Example Storage trigger on the create/finalize event
@app.storage('BUCKET_NAME', 'finalize')
def storage(event):
    app.log.info(event)
    return 

# Example middleware
@app.middleware()
def add_db(event):
    app.g.db = "db"
    return event
