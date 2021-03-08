=========
Resources
=========


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
