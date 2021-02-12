from goblet import Goblet, jsonify, Response
import logging 

app = Goblet(function_name="goblet_example",region='us-central-1', local="test")
app.log.setLevel(logging.INFO) # configure goblet logger level

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
@app.route('/home/{name}', methods=["GET"], param_types={"name":"integer"})
def namer(name):
    return name

# example response object
@app.route('/response')
def response():
    return Response({"failed":400},headers={"Content-Type":"application/json"}, status_code=400)

# scheduled job
@app.schedule('5 * * * *')
def scheduled_job():
    return jsonify("success")

# Example middleware
@app.middleware()
def add_db(event):
    app.g.db = "db"
    return event