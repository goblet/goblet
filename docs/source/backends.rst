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

You can pass in configurations to you cloudrun deployment in the `cloudrun` section in your `congig.json`. Parameters are 
key, value pairs that will be parsed and passed into the `gcloud run deploy command <https://cloud.google.com/sdk/gcloud/reference/run/deploy>`__. For flags pass in an empty string. 

.. code::json 

    {
        "cloudrun":{
            "max-instances": "1",
            "no-allow-authenticated: ""
        }
    }