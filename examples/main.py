from goblet import Goblet, jsonify, Response, goblet_entrypoint

app = Goblet(function_name="cloudfunctionv1-tagged", routes_type="cloudrun")
goblet_entrypoint(app)


# Typed Path Param
@app.route("/home/{name}/{id}", methods=["GET"])
def namer(name: str, id: int):
    return f"{name}: {id}"
