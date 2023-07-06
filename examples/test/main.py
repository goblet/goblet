import logging
from goblet import Goblet, goblet_entrypoint
from goblet.infrastructures.pubsub import PubSubClient

app = Goblet(function_name="create-pubsub-topic")

app.log.setLevel(logging.DEBUG)  # configure goblet logger level
goblet_entrypoint(app)

# Create pubsub topics
client: PubSubClient = app.pubsub_topic("goblet-created-test-topic")

@app.pubsub_subscription(topic="goblet-created-test-topic", use_subscription=True)
def subscription(data):
    return "success"