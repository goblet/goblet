from goblet import Goblet
import logging 

app = Goblet(function_name="goblet_example",region='us-central-1')
app.log.setLevel(logging.INFO) # configure goblet logger level

# Example middleware
@app.middleware()
def add_db(event):
    app.g.db = "db"
    return event

# example query args
@app.route('/home')
def query_args():
    request = app.current_request
    q = request.args.get("q")
    return app.jsonify(q)

# path param
@app.route('/home/{test}')
def home(test):
    return app.jsonify(test)

# POST request
@app.route('/home', methods=["POST"])
def post():
    request = app.current_request
    return app.jsonify(request.json)

# Typed Path Param
@app.route('/home/{name}', methods=["GET"], param_types={"name":"integer"})
def namer(name):
    return name