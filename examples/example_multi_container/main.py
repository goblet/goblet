#!/usr/bin/env python

import os
import logging
import sys
import json

from goblet import Goblet, goblet_entrypoint
import requests

logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

app = Goblet("opa", backend="cloudrun", routes_type="cloudrun")
goblet_entrypoint(app)


opa_url = os.environ.get("OPA_ADDR", "http://localhost:8181")
policy_path = os.environ.get("POLICY_PATH", "/v1/data/httpapi/authz")

def check_auth(url, input):

    logging.info("Checking input...")
    logging.info(json.dumps({"input":input}, indent=2))
    try:
        rsp = requests.post(url, data=json.dumps({"input":input}))
    except Exception as err:
        logging.info(err)
        return {}
    j = rsp.json()
    if rsp.status_code >= 300:
        logging.info("Error checking auth, got status %s and message: %s", j.status_code, j.text)
        return {}
    logging.info("Auth response:")
    logging.info(json.dumps(j, indent=2))
    return j

@app.route('/salary/{username}', methods=["POST", "GET"])
def root(username):

    url = opa_url + policy_path
 
    input = app.current_request.json
    j = check_auth(url, input).get("result", {})
    if j.get("allow", False):
        return "Success: user %s is authorized \n" % input["user"]
    return "Error: user %s is not authorized to %s url /%s \n" % (input["user"], app.current_request.method, f"salary/{username}")

if __name__ == "__main__":
    app.run()