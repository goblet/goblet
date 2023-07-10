import datetime

import logging
from goblet import Goblet, goblet_entrypoint
from goblet.infrastructures.pubsub import PubSubClient
from goblet_gcp_client import Client

app = Goblet(function_name="create-pubsub-topic")

app.log.setLevel(logging.DEBUG)  # configure goblet logger level
goblet_entrypoint(app)

# Create pubsub topics
client: PubSubClient = app.pubsub_topic("goblet-created-test-topic")

# Route that publishes to pubsub topic
@app.http()
def publish(request):
    should_fail = request.args.get("should_fail", False)
    message = "failure" if should_fail else "success"
    response = client.publish(
        message={
            'message': message,
            'time': datetime.datetime.now().isoformat()
        }
    )
    app.log.info(response)
    return {}


# Triggered by pubsub topic. Simulates failure to trigger DLQ
@app.pubsub_subscription("goblet-created-test-topic", dlq=True, dlq_alert=True, dlq_alert_config={
    # Trigger alert if 10 messages fail within 1 minute
    "trigger_value": 10,
})
def subscription(data: str):
    raise Exception("Simulating failure")

# Backfill route to pull from DLQ
@app.http(headers={"X-Backfill": "true"})
def backfill(request):
    num_messages = request.headers.get("X-Backfill-Num-Messages", 1)
    dlq_pull_subscription= request.headers.get("X-Backfill-DLQ-Pull-Subscription", "goblet-created-test-topic-dlq-pull-subscription")
    
    pubsub_client = Client(
        resource="pubsub",
        version="v1",
        calls="projects.subscriptions"
    )

    total_messages = 0
    received_message_length = -1
    ack_ids = []
    failed_ids = []
    while total_messages <= int(num_messages) and received_message_length != 0:
        # The subscriber pulls a specific number of messages. The actual
        # number of messages pulled may be smaller than max_messages.
        pull_response = pubsub_client.execute(
            "pull",
            parent_key="subscription",
            parent_schema=f"projects/{app.config.project_id}/subscriptions/{dlq_pull_subscription}",
            params={
                "body": {
                    "maxMessages": 10,
                }
            }
        )

        received_message_length = len(pull_response.received_messages)
        total_messages += received_message_length

        for received_message in pull_response.received_messages:
            decoded_data = received_message.message.data.decode()
            try:
                app.log.info(f"Backfilling message {decoded_data}")
                # TODO: Backfill logic here
                backfill_response = "success"
            except Exception as e:
                backfill_response = None
                failed_ids.append(received_message.ack_id)
                app.log.info(
                    f"Failed backfill for {dlq_pull_subscription} with error {str(e)}"
                )

            if backfill_response == "success":
                ack_ids.append(received_message.ack_id)
                # Acknowledges the received message so they will not be sent again.
                pubsub_client.execute(
                    "acknowledge",
                    parent_key="subscription",
                    parent_schema=f"projects/{app.config.project_id}/subscriptions/{dlq_pull_subscription}",
                    params={
                        "body": {
                            "ackIds": [received_message.ack_id]
                        }
                    }
                )

    app.log.info(
        f"Received {total_messages} messages: acknowledged {len(ack_ids)} messages and failed on {len(failed_ids)}"
    )
    
    return f"Received {total_messages} messages: acknowledged {len(ack_ids)} messages and failed on {len(failed_ids)}", 200

