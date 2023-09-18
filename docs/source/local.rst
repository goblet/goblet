======
Local
======

Run Locally
^^^^^^^^^^^

Running your functions locally for testing and debugging is easy to do with the goblet command `goblet local`. 
You can hit your functions endpoint at ``localhost:8080``.

You can have a custom local name by setting the local param in the goblet class

.. code:: python

    from goblet import Goblet

    app = Goblet(function_name="goblet_example", local='test')


Then run ``goblet local test``

Note: If you have both `http()` and `route("/")` in order to test the route locally make sure to add the header ``X-Envoy-Original-Path``. Otherwise the route will default to ``@http()``

.. code:: sh 

    curl localhost:8080/endpoint

The goblet app will run on port 8080 by default. You can specify a custom port with the ``-p`` flag. 

.. code:: sh 

    goblet local -p 6000

You can set environment variables defined in your `config.json` locally by passing in the `--set-env` flag. Note that 
this will pass through environment variables set in a stage as well if you specify the `--stage` flag. 

.. code:: sh 

    goblet local --set-env --stage dev

Building and Running locally using Docker 
#########################################

Make sure Docker Desktop and Docker CLI is installed, more information located here: <https://docs.docker.com/desktop/>

Refresh local credentials by running: `gcloud auth application-default login`

Set the GOOGLE_APPLICATION_CREDENTIALS variable by running: `export GOOGLE_APPLICATION_CREDENTIALS=~/.config/gcloud/application_default_credentials.json`

To build container run: `docker build . -t <tag>`

To start container run:

.. code:: sh

    docker run -p 8080:8080 \
        -v ~/.config/gcloud/application_default_credentials.json:/tmp/application_default_credentials.json:ro \
        -e GOOGLE_APPLICATION_CREDENTIALS=/tmp/application_default_credentials.json \
        -e GCLOUD_PROJECT=<gcp-project> <tag>:latest

Installing private packages during Docker Build
===============================================

To install a private package located with GCP Artifact Registry, credentials will need to be mounted during the build process. Add this line to Dockerfile before requirements install:

.. code:: Dockerfile

    RUN --mount=type=secret,id=gcloud_creds,target=/app/google_adc.json export GOOGLE_APPLICATION_CREDENTIALS=/app/google_adc.json \  
        && pip install -r requirements.txt

To build container run: `docker build . --secret id=gcloud_creds,src="$GOOGLE_APPLICATION_CREDENTIALS" -t <tag>`    

Scheduled Job 
#############

To test a scheduled job locally you will need to include two headers in your request. One ``X-Goblet-Type:schedule`` and 
``X-Goblet-Name:FUNCTION_NAME`` which is the name of your function.

.. code:: sh 

    curl -H X-Goblet-Type:schedule -H X-Goblet-Name:FUNCTION_NAME localhost:8080

Pubsub 
######

To test a pubsub topic locally you will need to include the subscription in the payload as well as a base64 encoded string for the body. 

.. code:: python 

    {
        "subscription": "TOPIC_NAME", 
        "body": base64.b64encode(json.dumps({"key":"value"}).encode())
    } 

Cloud Task
##########

To test a cloudtask locally you will need to add the ``User-Agent:Google-Cloud-Tasks`` and ``X-Goblet-CloudTask-Target:TARGET`` headers

.. code:: sh 

    curl -H X-Goblet-CloudTask-Target:TARGET -H User-Agent:Google-Cloud-Tasks localhost:8080

Eventarc
########

To test an eventarc event locally you will need to add ``Ce-Type`` and ``Ce-Source`` headers

.. code:: sh 
    
    curl -H Ce-Type:google.cloud.pubsub.topic.v1.messagePublished -H Ce-Sourc://pubsub.googleapis.com/projects/goblet/topics/test localhost:8080

Cloudrun Job 
############

To test a cloudrun job locally you can run `goblet job run APP_NAME-JOB_NAME TASK_ID`

BQ Remote Function
##################

To test an bqremotefunction locally you will need to add a ``userDefinedContext`` field to the body with a ``X-Goblet-Name`` field with the format of ``APP_NAME`` _ ``FUNCTION_NAME``.
You pass in the arguments to you function in a list in the ``calls`` field.


.. code:: python

    {
        "userDefinedContext": {
            "X-Goblet-Name": "bqremotefunction_test_function_test"
        },
        "calls": [[2, 2], [3, 3]],
    }

Log Levels
^^^^^^^^^^
You can set the log level by passing in the environent variable `GOBLET_LOG_LEVEL`. By default the log level is `INFO`. You can set the level 
to `DEBUG` by passing `--debug` after any goblet command. 

.. code:: console

    goblet --debug package


Debugging with VScode
^^^^^^^^^^^^^^^^^^^^^

To debug your functions locally with Vscode you can use the following configuration. Replace LOCAL_NAME with the name you 
passed into ``goblet(NAME, local=LOCAL_NAME)``. Make sure that there are no naming collisions with any function names used in your app.

.. code:: json 

    {
        "configurations": [
            {
                "name": "Python: Module",
                "type": "python",
                "request": "launch",
                "module": "functions_framework",
                "args": [
                    "--target",
                    "LOCAL_NAME",
                    "--debug"
                ]
            }
        ]
    }