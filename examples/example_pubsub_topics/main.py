import datetime

from goblet import Goblet, goblet_entrypoint
import logging
from goblet.infrastructures.pubsub import PubSubClient

app = Goblet(function_name="create-pubsub-topic")

app.log.setLevel(logging.DEBUG)  # configure goblet logger level
goblet_entrypoint(app)

# Create pubsub topics
client: PubSubClient = app.pubsub_topic("goblet-created-test-topic")

# Route that publishes to pubsub topic
@app.http()
def publish(request):
    response = client.publish(
        message={
            'hello': 'worlds!',
            'time': datetime.datetime.now().isoformat()
        }
    )
    app.log.info(response)
    return {}


# Triggered by pubsub topic
@app.pubsub_subscription("goblet-created-test-topic", dlq=True)
def topic(data):
    app.log.info(data)
    # Simulates failure to trigger DLQ
    return "Internal Server Error", 500

# Triggered by DLQ topic
@app.pubsub_subscription("goblet-created-test-topic-dlq")
def dlq_topic(data):
    app.log.info(data)
    return
