=========
Resources
=========

Http
^^^^
You can have a http endpoint that can be triggered by calling the cloudfunction directly. This is the simpliest endpoint and will
only deploy a cloudfunction. The function takes in a flask request object

.. code:: python 

    from goblet import Goblet

    app = Goblet(function_name='simple_http')

    @app.http()
    def http_entrypoint(request):
        return request.json


You can have multiple http endpoints that get triggered based on the request headers. Note if multiple header filters match, only the first match will be 
triggered.


The following endpoint will be triggered on any request that has a "X-Github-Event" header

.. code:: python 

    @app.http(headers={"X-Github-Event"})
    def main(request):
        return jsonify(request.json)

The following endpoints will be triggered if the request contains a "X-Github-Event" header that matches the corresponding value

.. code:: python 

    @app.http(headers={"X-Github-Event": "issue"})
    def main(request):
        return jsonify("triggered on issue")

    @app.http(headers={"X-Github-Event": "pr"})
        def main(request):
            return jsonify("triggered on pr")

Routes
^^^^^^

The Goblet.route() method is used to construct which routes you want to create for your API. 
Behind the scenese goblet will configure an Api Config and Api Gateway on gcp.

The concept of routes are the same mechanism used by Flask. You decorate a function with ``@app.route(...)``, 
and whenever a user requests that URL from the api gateway url, the function you’ve decorated is called. For example, 
suppose you deployed this app:

.. code:: python 

    from goblet import Goblet

    app = Goblet(function_name='helloworld')

    @app.route('/')
    def index():
        return {'view': 'index'}

    @app.route('/a')
    def a():
        return {'view': 'a'}

    @app.route('/b')
    def b():
        return {'view': 'b'}

If you go to https://endpoint/, the index() function would be called. If you went to https://endpoint/a and https://endpoint/b, then the a() and b() function would be called, respectively.

You can also create a route that captures part of the URL. This captured value will then be passed in as arguments to your view function:

.. code:: python 

    @app.route('/users/{name}')
    def users(name):
        return {'name': name}

If you then go to https://endpoint/users/james, then the view function will be called as: users('james'). 
The parameters are passed as keyword parameters based on the name as they appear in the URL. 
The argument names for the view function must match the name of the captured argument:

.. code:: python 

    @app.route('/a/{first}/b/{second}')
    def users(first, second):
        return {'first': first, 'second': second}


Scheduled Jobs
^^^^^^^^^^^^^^

To deploy scheduled jobs using a cron schedule use the ``@app.schedule(...)`` decorator. The cron schedule follows the unix-cron format. 
More information on the cron format can be found `here`_. Make sure `Cloud Scheduler`_ is enabled in your account if you want to deploy
scheduled jobs.

Example usage:

.. code:: python 

    @app.schedule('5 * * * *')
    def scheduled_job():
        return app.jsonify("success")

You can pass in additional fields to your schedule to add custom headers, body, and method using the types defines for `job <https://cloud.google.com/scheduler/docs/reference/rest/v1/projects.locations.jobs#Job>`__.

.. code:: python 

    @app.schedule('5 * * * *', headers={"x-cron": "5 * * * *"}, body="a base64-encoded string")
    @app.schedule('6 * * * *', headers={"x-cron": "6 * * * *"}, body="another base64-encoded string")
    @app.schedule('10 * * * *', httpMethod="POST")
    def scheduled_job():
        app.current_request.body
        app.current_request.headers
        return app.jsonify("success")

Note that several of customizable fields require specific formats which include `body` which is a base64 encoded string. In order 
to use a json field for the body you would need to use the following code

..code:: python 

    base64.b64encode(json.dumps({"key":"value"}).encode('utf-8')).decode('ascii')

and then in your function you would decode the body using 

..code:: python 

    json.loads(base64.b64decode(raw_payload).decode('utf-8'))

Another unique field is `attemptDeadline` which requires a duration format such as `3.5s`


.. _HERE: https://cloud.google.com/scheduler/docs/configuring/cron-job-schedules
.. _CLOUD SCHEDULER: https://cloud.google.com/scheduler

PubSub
^^^^^^

You can trigger endpoints from pubsub using the ``@app.topic(...)`` decorator. All that is required is the topic name. You can optionally 
provide an attribute dictionary which will only trigger the function if the pubsub message attributes matches those defined in the decorator.

Example usage:

.. code:: python 

    # pubsub topic
    @app.topic('test')
    def topic(data):
        app.log.info(data)
        return 

    # pubsub topic with matching message attributes
    @app.topic('test', attributes={'key': 'value'})
    def home2(data):
        app.log.info(data)
        return 

Storage
^^^^^^^

You can trigger functions from storage events using the ``@app.storage(BUCKET, EVENT)`` decorator. It is required to pass in the bucket name and the event_type.
The following events are supported by GCP 

* finalize
* delete
* archive
* metadataUpdate

Example usage:

.. code:: python 

    @app.storage('BUCKET_NAME', 'finalize')
    def storage(event):
        app.log.info(event)

To trigger a function on multiple events or multiple buckets you can specify multiple decorators.

.. code:: python 

    @app.storage('BUCKET_NAME', 'archive')
    @app.storage('BUCKET_NAME', 'delete')
    @app.storage('BUCKET_NAME2', 'finalize')
    def storage(event):
        app.log.info(event)