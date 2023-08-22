import logging
import sys

from goblet import Goblet, goblet_entrypoint

logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

app = Goblet("multi-container", backend="cloudrun", routes_type="cloudrun")
goblet_entrypoint(app)


@app.route('/test', methods=["POST", "GET"])
def test():
    return "api container"
