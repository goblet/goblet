from goblet import Goblet

app = Goblet(function_name="eml-watcher",region='us-central-1', stackdriver=True, debug=True)

email_schema = {
     "type" : "object",
     "properties" : {
         "name" : {"type" : "string"},
         "Id" : {"type" : "number"},
     },
 }


@app.entry_point(event_schema=email_schema)
def main(event, context):
    app.log.info("test")
    app.log.error("test error")


if __name__ == "__main__":
    main({'@type': 'type.googleapis.com/google.pubsub.v1.PubsubMessage', 'attributes': {"event_type":"test"},  'data': 'eyJlbWFpbEFkZHJlc3MiOiJyZXBvcnQtcGhpc2hpbmctZXVAY3liZXJuZXRleC5haSIsImhpc3RvcnlJZCI6Mjc4OTIyfQ=='},{} )