========
Features
========


Input/Output validation
--------------------------

goblet uses `json schema <https://json-schema.org/understanding-json-schema/basics.html>`_ underneath to preform json validation. To use with goblet
create your schema and pass into the goblet wrapper. If valid goblet will decode (default json decode) the event data.

.. code::

    from goblet import Goblet

    app = Goblet()
    example_schema = {
        "type" : "object",
        "properties" : {
            "name" : {"type" : "string"},
            "Id" : {"type" : "number"},
        },
    }


    @app.entry_point(event_schema=example_schema)
    def main(event, context):
        app.log.info(app.data)

event 1 will pass:

.. code::
    
    {
        "name": "test_user",
        "Id" : 1
    }

event 2 will fail and log error to stackdriver:

.. code::
   
    {
        "incorrect_field": "not what i wanted"
    }

Output validation to another pubsub topic can be done when configuring the topic with goblet.

.. code::

    from goblet import Goblet

    app = Goblet()
    example_schema = {
        "type" : "object",
        "properties" : {
            "name" : {"type" : "string"},
            "Id" : {"type" : "number"},
        },
    }

    app.configure_pubsub_topic("next_pubsub_function",schema=example_schema)


    @app.entry_point()
    def main(event, context):
        app.publish( {"name": "test_user","Id" : 1}) # valid
