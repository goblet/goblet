import datetime

from goblet import Goblet, goblet_entrypoint
import logging
from goblet.infrastructures.pubsub import PubSubClient

app = Goblet(function_name="create-pubsub-topic", backend="cloudrun")

app.log.setLevel(logging.INFO)  # configure goblet logger level
goblet_entrypoint(app)

client: PubSubClient = app.pubsub_topic("goblet-created-test-topic", config={
    "labels": {
        "ochestrator": "goblet",
        "environment": "dev"
    }
})

another_client: PubSubClient = app.pubsub_topic("another-goblet-created-test-topic", config={
    "labels": {
        "ochestrator": "goblet",
        "environment": "dev"
    }
})


@app.route('/publish', methods=['GET'])
def publish():
    response = client.publish(
        message={
            'hello': 'worlds!',
            'time': datetime.datetime.now().isoformat()
        }
    )
    app.log.info(response)
    return {}


@app.pubsub_subscription("goblet-created-test-topic")
def topic(data):
    app.log.info(data)
    return

@app.topic("another-goblet-created-test-topic")
def same_topic(data):
    app.log.info(data)
    return