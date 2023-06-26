========
Handlers
========

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

By default there is a timeout on api gateway of 15 seconds. This can be overriden by setting `"api_gateway": {"deadline": 45}` in `config.json`. You 
can configure a per route deadline by passing in the deadline parameter in your route. 

.. code:: python 

    @app.route('/deadline', deadline=10)
    def deadline():
        return 'custom_deadline'

By default routes are deployed to an api gateway. For cloudrun you have the option to use `route_type=cloudrun` to simply use the cloudrun 
instance itself. The routes work the same as with an apigateway, but you would access the api via the cloudrun url instead of the api gateway url.

.. code:: python 

    app = Goblet(function_name="cloudrun-routing", routes_type="cloudrun", backend="cloudrun")

Scheduled Jobs
^^^^^^^^^^^^^^

To deploy scheduled jobs using a cron schedule use the `@app.schedule(...)` decorator. The cron schedule follows the unix-cron format. 
More information on the cron format can be found in the `gcp docs <https://cloud.google.com/scheduler/docs/configuring/cron-job-schedules>`_. Make sure `Cloud Scheduler <https://cloud.google.com/scheduler>`_ is enabled in your account if you want to deploy
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

.. code:: python 

    base64.b64encode(json.dumps({"key":"value"}).encode('utf-8')).decode('ascii')

and then in your function you would decode the body using 

.. code:: python 

    json.loads(base64.b64decode(raw_payload).decode('utf-8'))

Another unique field is `attemptDeadline` which requires a duration format such as `3.5s`

To test your scheduled jobs locally you will need to pass a `X-Goblet-Type` header with the value `schedule` and a `X-Goblet-Name` header
with the name of your scheduled function.

For example: 

.. code::

    "X-Goblet-Type": "schedule",
    "X-Goblet-Name": FUNCTION_NAME

PubSub
^^^^^^

You can trigger endpoints from pubsub using the ``@app.pubsub_subscription(...)`` decorator. All that is required is the topic name. You can optionally 
provide an attribute dictionary which will only trigger the function if the pubsub message attributes matches those defined in the decorator.
If using cloudrun backend or `use_subscription=true` the attributes will be created as a filter on the subscription itself. You can also pass in 
a custom `filter` as well. Note that filters are not able to be modified once they are applied to a subscription. 

In addition to filters you can also add configuration values that will be passed directly to the subscription. 
By setting `config={"enableExactlyOnceDelivery": True}` you can enable exactly delivery to ensure messages are not redelivered once acknowledged.
For additional information on configuration values available see `PubSub Subscription Fields <https://cloud.google.com/pubsub/docs/reference/rest/v1/projects.subscriptions/create#request-body>`__

Example usage:

.. code:: python 

    # pubsub topic
    @app.pubsub_subscription('test')
    def topic(data):
        app.log.info(data)
        return 

    # pubsub topic with matching message attributes
    @app.pubsub_subscription('test', attributes={'key': 'value'})
    def home2(data):
        app.log.info(data)
        return 

    # pubsub topic in a different project
    @app.pubsub_subscription('test', project="CROSS_PROJECT")
    def cross_project(data):
        return 

    # create a pubsub subscription instead of pubsub triggered function
    @app.pubsub_subscription('test', use_subscription=True)
    def pubsub_subscription_use_subscription(data):
        return 

    # create a pubsub subscription instead of pubsub triggered function and add filter
    @app.pubsub_subscription('test', use_subscription=True, filter='attributes.name = "com" AND -attributes:"iana.org/language_tag"')
    def pubsub_subscription_filter(data):
        return 

    # switching the pubsub topic to a different project requires force_update, since it requires the subscription to be recreated
    @app.pubsub_subscription('test', project="NEW_CROSS_PROJECT", force_update=True)
    def cross_project(data):
        return 

To test a pubsub topic locally you will need to include the subscription in the payload as well as a base64 encoded string for the body. 

.. code:: python 

    {
        "subscription": "TOPIC_NAME", 
        "body": base64.b64encode(json.dumps({"key":"value"}).encode())
    } 

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

Eventarc
^^^^^^^^

You can trigger functions from evenarc events using the `@app.eventarc(topic=None, event_filters=[])` decorator. Specifying a topic will create a trigger on a custom pubsub topic. For 
all other events, specify the event attribute  and event value in the `event_filters` list. See `Creating Triggers <https://cloud.google.com/eventarc/docs/creating-triggers#trigger-gcloud>`__ for more information
on possible values.

Example usage:

.. code:: python 

    # Example eventarc pubsub topic
    @app.eventarc(topic="test")
    def pubsub(data):
        app.log.info("pubsub")
        return


    # Example eventarc direct event
    @app.eventarc(
        event_filters=[
            {"attribute": "type", "value": "google.cloud.storage.object.v1.finalized"},
            {"attribute": "bucket", "value": "BUCKET"},
        ],
        region="us-east1",
    )
    def bucket(data):
        app.log.info("bucket_post")
        return


    # Example eventarc audit log
    @app.eventarc(
        event_filters=[
            {"attribute": "type", "value": "google.cloud.audit.log.v1.written"},
            {"attribute": "methodName", "value": "storage.objects.get"},
            {"attribute": "serviceName", "value": "storage.googleapis.com"},
        ],
        region="us-central1",
    )
    def bucket_get(data):
        app.log.info("bucket_get")
        return

To test an eventarc event locally you will need to add ``Ce-Type`` and ``Ce-Source`` headers

.. code:: sh 
    
    curl -H Ce-Type:google.cloud.pubsub.topic.v1.messagePublished -H Ce-Sourc://pubsub.googleapis.com/projects/goblet/topics/test localhost:8080


Jobs
^^^^

You can create and trigger cloudrun jobs using the `@app.job(...)` decorator. If you would like to trigger multiple tasks in one job execution 
you can specify multiple decorators with a different `task_id`. Any custom job configurations such as a schedule should be added to the `task_id=0`. Jobs can be further configured
by setting various configs in `config.json.` 

`job_spec` can be found at `Cloudrun Jobs Spec  <https://cloud.google.com/run/docs/reference/rest/v2/TaskTemplate>`__

`job_container` can be found at `Cloudrun Jobs Container  <https://cloud.google.com/run/docs/reference/rest/v2/Container>`__

You can schedule executions by passing in a cron `schedule` to the first task. Each job task function takes in the task id. 

To test a job locally you can run `goblet job run APP_NAME-JOB_NAME TASK_ID`

Example usage:

.. code:: python 

    @app.job("job1", schedule="* * * * *")
    def job1_task1(id):
        app.log.info(f"job...{id}")
        return "200"

    @app.job("job1", task_id=1)
    def job1_task2(id):
        app.log.info(f"different task for job...{id}")
        return "200"
    
    @app.job("job2")
    def job2(id):
        app.log.info(f"another job...{id}")
        return "200"

See the example `config.json <https://github.com/goblet/goblet/blob/main/examples/example_cloudrun_job/config.json>`__

BigQuery Remote Functions
^^^^^^^^^^^^^^^^^^^^^^^^^

To deploy BigQuery remote functions use ``@app.bqremotefunction(...)`` decorator.
BigQuery remote functions documentation can be found `here <https://cloud.google.com/bigquery/docs/reference/standard-sql/remote-functions>`_.

Example usage:

.. code:: python

    @app.bqremotefunction(dataset_id=...)
    def my_remote_function(x: str, y: str) -> str:
        return f"input parameters are {x} and {y}"

Allowed data type can be found `data types for remote functions <https://cloud.google.com/bigquery/docs/reference/standard-sql/data-types>`_.
The routine name on BigQuery will be <goblet_function_name>_<remotefunction_name>.

As an example:

.. code:: python

    from goblet import Goblet, goblet_entrypoint

    app = Goblet(function_name="my_functions")
    goblet_entrypoint(app)

    @app.bqremotefunction(dataset_id="my_dataset_id")
    def my_routine(x: str, y: str) -> str:
        return f"Name: {x} LastName: {y}"

Creates a routine named my_functions_my_routine with two strings as
input parameters with names x and y and return a formatted string. The dataset id
will be "my_dataset_id".

The dataset_id reference a dataset in BigQuery already created in the same
location and project in GCP.

To call a routine from BigQuery just use

.. code:: sql

    select PROJECT.my_dataset_id.my_functions_my_routine(name, last_name) from my_dataset_id.table

This will apply my_functions_my_routine to every tuple present in table
my_dataset_id.table passing fields name and last_name from the table as inputs.
Data type inputs for the routine used in BigQuery query must match with data types used in the python function
definition. In the example above select will return as many single-tuple value as tuples
exist in the table.


Another example:

.. code:: python

    from goblet import Goblet, goblet_entrypoint

    app = Goblet(function_name="math_example")
    goblet_entrypoint(app)
    @app.bqremotefunction(dataset_id="blogs")
    def multiply(x: int, y: int, z: int) -> int:
        w = x * y * z
        return w

Should be called this way:

.. code:: sql

    select PROJECT.my_dataset_id.math_example_multiply(x,y,z) from my_dataset_id.table

And will return an integer resulting from the multiplication from the three fields
x,y,z in table my_dataset_id.table for every tuple in the table.


When deploying a BigQuery remote function, Goblet creates the resources in GCP: a
`BigQuery connection <https://cloud.google.com/bigquery/docs/reference/bigqueryconnection>`_,
a `BigQuery routine <https://cloud.google.com/bigquery/docs/reference/rest/v2/routines>`_ and
a cloudfunction or cloudrun (depending on the parameter backend used in Goblet instantiation).


To test an bqremotefunction locally you will need to add a ``userDefinedContext`` field to the body with a ``X-Goblet-Name`` field with the format of ``APP_NAME`` _ ``FUNCTION_NAME``.
You pass in the arguments to you function in a list in the ``calls`` field.


.. code:: python

    {
        "userDefinedContext": {
            "X-Goblet-Name": "bqremotefunction_test_function_test"
        },
        "calls": [[2, 2], [3, 3]],
    }


CloudTask Target
^^^^^^^^^^^^^^^^

You can handle http requests from a CloudTask by using the ``@app.cloudtasktarget(name="target")`` decorator.
For Goblet to route a request to a function decorated with ``cloudtasktarget(name="target")``, the request must include
the following headers:

.. code::

    "User-Agent": "Google-Cloud-Tasks",
    "X-Goblet-CloudTask-Target": "target"

.. note::
    * Goblet uses the `User-Agent` headers to route the request to the CloudTaskTarget instance. The CloudTask Queue adds this headers.
    * The `X-Goblet-CloudTask-Target` routes the request to the expected function.


The next example shows the function that would serve a request with the headers shown above.

.. code:: python

    from goblet import Goblet, goblet_entrypoint

    app = Goblet(function_name="cloudtask_example")
    goblet_entrypoint(app)

    @app.cloudtasktarget(name="target")
    def my_target_handler(request):
        ''' handle request '''
        return



Another example using ``app.cloudtaskqueue`` to queue and handle tasks in the same instance.

.. code:: python

    from goblet import Goblet, goblet_entrypoint

    app = Goblet(function_name="cloudtask_example")
    goblet_entrypoint(app)

    client = app.cloudtaskqueue("queue")
    @app.cloudtasktarget(name="target")
    def my_target_handler(request):
        ''' handle request '''
        return {}


    @app.route("/enqueue", methods=["GET"])
    def enqueue():
        payload = {"message": {"title": "enqueue"}}
        client.enqueue(target="target", payload=payload)
        return {}
