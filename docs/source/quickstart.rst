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

    python3 -m pip install goblet-gcs


You can verify you have goblet installed by running:

.. code::

    $ goblet --help
    Usage: goblet [OPTIONS] COMMAND [ARGS]...
    ...

Credentials
************

Before you can deploy an application, be sure you have credentials configured. You should run `gcloud auth login` and sign in to the desired project.

When setting the defaut location note tha api-gateway is only available in `asia-east1`, `europe-west1`, and `us-central1`.

Creating Your Project
*********************

create your project directory, which should include an main.py and a requirements.txt. Make sure requirements.txt includes `goblet-gcs`

.. code::

    $ ls -la
    drwxr-xr-x   .goblet
    -rw-r--r--   main.py
    -rw-r--r--   requirements.txt

You can ignore the .goblet directory for now, the two main files we'll focus on is app.py and requirements.txt.

Let's take a look at the main.py file:

.. code:: python

    from goblet import Goblet

    app = Goblet(function_name="goblet_example",region='us-central-1')

    @app.route('/home')
    def index():
        return {"hello": "world"}


This app with deploy an api with endpoint `/home`.

Deploying
**********

Let's deploy this app. Make sure you're in the app directory and run goblet deploy:

.. code::

    $ goblet deploy
    INFO:goblet.deployer:zipping function......
    INFO:goblet.deployer:uploading function zip to gs......
    INFO:goblet.deployer:creating google function......
    INFO:goblet.deployer:deploying api......
    INFO:goblet.deployer:api successfully deployed...
    INFO:goblet.deployer:api endpoint is goblet-example-yol8sbt.uc.gateway.dev
    ```

You now have an API up and running using API Gateway and cloudfunctions:

.. code::

    $ curl https://goblet-example-yol8sbt.uc.gateway.dev/home
    {"hello": "world"}

Try making a change to the returned dictionary from the home() function. You can then redeploy your changes by running `golet deploy`.


