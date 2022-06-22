========
Backends
========

Cloudfunction
^^^^^^^^^^^^^

The default backend. 

Cloudrun
^^^^^^^^

You can deploy your function to cloudrun updating the backend paramter to main Goblet class.

.. code::python

    app = Goblet(backend="cloudrun")

.. note::
    The function name for cloudrun must use only lowercase alphanumeric characters and dashes, cannot begin or end with a dash, and cannot be longer than 63 characters

You can pass in configurations to you cloudrun deployment in the `cloudrun` section in your `config.json`. Parameters are 
key, value pairs that will be parsed and passed into the `gcloud run deploy command <https://cloud.google.com/sdk/gcloud/reference/run/deploy>`__. For flags pass in an empty string. 

.. code:: json 

    {
        "cloudrun":{
            "max-instances": "1",
            "set-env-vars": "ENV1=env1",
            "no-traffic": ""
        }
    }

Deploying to cloudrun requires either a Dockerfile or Procfile in the directory you are looking to deploy your goblet app. If neither
of those files are found, then goblet will create a default Dockerfile that allows the app to be build, deployed, and run correctly. 
Having a custom Dockerfile if only needed if you would like to customize you container at all. The default command in the Dockerfile
is `functions-framework --target=goblet_entrypoint` and the default port is 8080. These can be overriden  in `config.json`

.. code:: json 

    {
        "cloudrun":{
            "command": "override command",
            "port": 5000
        }
    }