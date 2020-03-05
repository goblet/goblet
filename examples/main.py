from goblet import Goblet
import logging 

app = Goblet(function_name="goblet_example",region='us-central-1', stackdriver=True)
app.log.setLevel(logging.INFO) # configure goblet logger level

# json schema to validate input
example_schema = {
     "type" : "object",
     "properties" : {
         "name" : {"type" : "string"},
         "Id" : {"type" : "number"},
     },
 }

app.configure_pubsub_topic("next_pubsub_function",schema=example_schema)


@app.entry_point(event_schema=example_schema)
def main(event, context):
    app.log.info(app.data)
    app.log.error("test error")

    # publish to new pubsub topic
    app.publish( {"name": "test_user","Id" : 1}) # valid


if __name__ == "__main__":
    main({'@type': 'type.googleapis.com/google.pubsub.v1.PubsubMessage', 'attributes': {"event_type":"test"},  'data': 'eyJlbWFpbEFkZHJlc3MiOiJyZXBvcnQtcGhpc2hpbmctZXVAY3liZXJuZXRleC5haSIsImhpc3RvcnlJZCI6Mjc4OTIyfQ=='},{} )