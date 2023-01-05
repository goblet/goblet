import json
import os

from goblet.utils import get_g_dir, get_dir
from goblet.__version__ import __version__


def create_goblet_dir(name):
    """Creates a new goblet directory with a sample main.py, requirements.txt, and config.json"""
    try:
        os.mkdir(get_g_dir())
    except FileExistsError:
        pass
    with open(f"{get_g_dir()}/config.json", "w") as f:
        f.write(json.dumps({"cloudfunction": {}}, indent=4))
    with open("requirements.txt", "w") as f:
        f.write(f"goblet-gcp=={__version__}")
    with open("main.py", "w") as f:
        f.write(
            f"""from goblet import Goblet, jsonify,goblet_entrypoint

app = Goblet(function_name="goblet-{name}")
goblet_entrypoint(app)

@app.http()
def main(request):
    return jsonify(request.json)

# route
# @app.route('/hello')
# def home():
#     return jsonify("goodbye")

# schedule
# @app.schedule('5 * * * *')
# def scheduled_job():
#     return jsonify("success")

# pubsub topic
# @app.topic('test_topic')
# def topic(data):
#     app.log.info(data)
#     return
"""
        )
    with open("README.md", "w") as f:
        f.write(
            f"""# goblet-{name}

autocreated by goblet

To test endpoints locally run `goblet local`
To deploy cloudfunctions and other gcp resources defined in `main.py` run `goblet deploy`

To check out goblet documentation go to [docs](https://goblet.github.io/goblet/docs/build/html/index.html)
"""
        )


def write_dockerfile():
    with open(f"{get_dir()}/Dockerfile", "w") as f:
        f.write(
            """\
# https://hub.docker.com/_/python
FROM python:3.10-slim

# setup environment
ENV APP_HOME /app
WORKDIR $APP_HOME

# install keyring backend to handle artifact registry authentication
# RUN pip install keyrings.google-artifactregistry-auth==1.1.1

# Install dependencies.
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy local code to the container image.
COPY . .
"""
        )
