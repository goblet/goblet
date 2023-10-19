import os
import logging
import datetime
from goblet.infrastructures.pubsub import PubSubClient
from goblet import Goblet, goblet_entrypoint

# Set the PUBSUB_EMULATOR_HOST environment variable to the emulator's host:port
os.environ["PUBSUB_EMULATOR_HOST"] = "localhost:8085"
os.environ["GOBLET_LOCAL_URL"] = "http://host.docker.internal:8080"

# Create a Goblet app
app = Goblet(function_name="create-pubsub-topic")

# Set the log level to DEBUG
app.log.setLevel(logging.DEBUG)
# Initialize Goblet
goblet_entrypoint(app)

# Create a Pub/Sub client
client: PubSubClient = app.pubsub_topic("goblet-created-test-topic")


@app.pubsub_subscription("goblet-created-test-topic", use_subscription=True)
def test_topic_handler(event):
    """
    Handler function for the 'goblet-created-test-topic' Pub/Sub subscription.
    """
    app.log.info(event)
    return "OK"


@app.route("/send")
def index():
    """
    Endpoint for sending a test message to the 'goblet-created-test-topic' Pub/Sub topic.
    """
    response = client.publish(
        message={"message": "test", "time": datetime.datetime.now().isoformat()}
    )
    app.log.info(response)
    return "ok"
