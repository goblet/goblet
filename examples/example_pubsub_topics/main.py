import datetime

from goblet import Goblet, goblet_entrypoint
import logging
from goblet.infrastructures.pubsub import PubSubClient

app = Goblet(function_name="create-pubsub-topic")

app.log.setLevel(logging.INFO)  # configure goblet logger level
goblet_entrypoint(app)

# Create pubsub topics
client: PubSubClient = app.pubsub_topic("goblet-created-test-topic")

# Route that publishes to pubsub topic
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


# Triggered by pubsub topic
@app.pubsub_subscription("goblet-created-test-topic")
def topic(data):
    app.log.info(data)
    return
