========
Backends
========

Cloudfunction
^^^^^^^^^^^^^

The default backend. 

Cloudrun
^^^^^^^^

You can deploy your function to cloudrun updating the backend parameter to main Goblet class.

.. code:: python

    app = Goblet(backend="cloudrun")

.. note::
    The function name for cloudrun must use only lowercase alphanumeric characters and dashes, cannot begin or end with a dash, and cannot be longer than 63 characters

You can pass in configurations to your cloudrun deployment in the `cloudrun` section in your `config.json`. 

Supported configurations include:

- traffic: assigns a custom amount of traffic to the latest revision and decreases previous revisions' traffic proportionally. If the service is brand new, the traffic will always default to 100%.

.. code:: json 

    {
        "cloudrun":{
            "traffic": 25
        }
    }

Deploying to cloudrun requires either a Dockerfile or Procfile in the directory you are looking to deploy your goblet app. If neither
of those files are found, then goblet will create a default Dockerfile that allows the app to be build, deployed, and run correctly. 
Having a custom Dockerfile if only needed if you would like to customize you container at all. 

For `revision configurations <https://cloud.google.com/run/docs/reference/rest/v2/projects.locations.services#RevisionTemplate>`__, pass values into `cloudrun_revision` section in your `config.json`. If you're using a service account, this is where to put it.

.. code:: json 

    {
        "cloudrun_revision":{
            "serviceAccount": "service-account@project.iam.gserviceaccount.com"
        }
    }

For `Cloud Build configurations <https://cloud.google.com/build/docs/api/reference/rest/v1/projects.builds>`__, pass values into `cloudbuild`

In order to set a custom artifact registry, use the "artifact_registry" configuration. If you would like to use an artifact registry from a different project, a service account with storage permissions in the current project's bucket and read + write in the other project's artifact registry will be necessary.

.. code:: json 

    {
        "cloudbuild":{
            "artifact_registry": "location-docker.pkg.dev/gcp_project/artifact/image"
            "serviceAccount": "service-account@project.iam.gserviceaccount.com"
        }
    }
