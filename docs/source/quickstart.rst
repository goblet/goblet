===========
Quickstart
===========

Getting Started
***************

In this tutorial, you'll use the goblet command line utility to create and deploy a basic REST API. This quickstart uses Python 3.7. You can find the latest versions of python on the Python download page.

To install Goblet, we'll first create and activate a virtual environment in python3.7:

.. code::

    $ python3 --version
    Python 3.7.3
    $ python3 -m venv venv37
    $ . venv37/bin/activate

Next we'll install Goblet using pip:

.. code::

    python3 -m pip install goblet-gcp


You can verify you have goblet installed by running:

.. code::

    $ goblet --help
    Usage: goblet [OPTIONS] COMMAND [ARGS]...
    ...

Credentials
************

Before you can deploy an application, be sure you have credentials configured. You should run ``gcloud auth application-default login`` and sign in to the desired project.

When setting the defaut location note that api-gateway is only available in ``asia-east1``, ``europe-west1``, and ``us-central1``.

Creating Your Project
*********************

create your project directory, which should include an main.py and a requirements.txt. Make sure requirements.txt includes ``goblet-gcp``

.. code::

    $ ls -la
    drwxr-xr-x   .goblet
    -rw-r--r--   main.py
    -rw-r--r--   requirements.txt

You can ignore the .goblet directory for now, the two main files we'll focus on is app.py and requirements.txt.

Let's take a look at the main.py file:

.. code:: python

    from goblet import Goblet, goblet_entrypoint

    app = Goblet(function_name="goblet_example")
    goblet_entrypoint(app)

    @app.route('/home')
    def home():
        return {"hello": "world"}


This app with deploy an api with endpoint ``/home``.

Running Locally
***************

Running your functions locally for testing and debugging is easy to do with goblet. 

Simply run ``goblet local``.

You can hit your functions endpoint at ``localhost:8080`` ar your defined routes.

To test your scheduled jobs locally you will need to pass a `X-Goblet-Type` header with the value `schedule` and a `X-Goblet-Name` header
with the name of your scheduled function.

For example: 

.. code::

    "X-Goblet-Type": "schedule",
    "X-Goblet-Name": FUNCTION_NAME


Deploying
**********

Let's deploy this app. Make sure you're in the app directory and run goblet deploy making sure to specify the desired location:

.. code::

    $ goblet deploy -l us-central1
    INFO:goblet.deployer:zipping function......
    INFO:goblet.deployer:uploading function zip to gs......
    INFO:goblet.deployer:function code uploaded
    INFO:goblet.deployer:creating cloudfunction......
    INFO:goblet.deployer:deploying api......
    INFO:goblet.deployer:api successfully deployed...
    INFO:goblet.deployer:api endpoint is goblet-example-yol8sbt.uc.gateway.dev
    ```

You now have an API up and running using API Gateway and cloudfunctions:

.. code::

    $ curl https://goblet-example-yol8sbt.uc.gateway.dev/home
    {"hello": "world"}

Try making a change to the returned dictionary from the home() function. You can then redeploy your changes by running ``golet deploy``.

Cleanup
**********

You've now created your first app using goblet. You can make modifications to your main.py file and rerun goblet deploy to redeploy your changes.

If you're done experimenting with Goblet and you'd like to cleanup, you can use the ``goblet destroy`` command making sure to specify the desired location, and Goblet will delete all the resources it created when running the goblet deploy command.

.. code:: bash

    $ goblet destroy -l us-central1
    INFO:goblet.deployer:destroying api gateway......
    INFO:goblet.deployer:api configs destroying....
    INFO:goblet.deployer:apis successfully destroyed......
    INFO:goblet.deployer:deleting google cloudfunction......
    INFO:goblet.deployer:deleting storage bucket......
