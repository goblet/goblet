================
Infrastructure
================

You can now provision infrastructure within your Goblet code.

Alerts
^^^^^^

You can deploy alerts related to your application by using the alert method. Each alert takes a name and a list of conditions. Notification channels
can be added to the `alerts.notification_channel` key in `config.json` or explicity in the alert. The base `AlertCondition` class allows you to 
fully customize your alert based on the fields privided by the `GCP Alert Resource <https://cloud.google.com/monitoring/api/ref_v3/rest/v3/projects.alertPolicies#conditionhttps://cloud.google.com/monitoring/api/ref_v3/rest/v3/projects.alertPolicies#condition>`_

If you do not need a fully customized alert you can use the built in classes for `MetricCondition`, `LogMatchCondition`, and `CustomMetricCondition`. These come with 
defaults in terms of duration and aggregations, but can be overriden as needed. The `CustomMetricCondition` creates a custom metric based on the filter provided and then 
creates an alert using that metric.  

.. code:: python

    from goblet.resources.alerts import MetricCondition,LogMatchCondition,CustomMetricCondition
    app = Goblet()
    
    # Example Metric Alert for the cloudfunction metric execution_count with a threshold of 10
    app.alert("metric",conditions=[MetricCondition("test", metric="cloudfunctions.googleapis.com/function/execution_count", value=10)])

    # Example Log Match metric that will trigger an incendent off of any Error logs
    app.alert("error",conditions=[LogMatchCondition("error", "severity>=ERROR")])

    # Example Metric Alert that creates a custom metric for severe errors with http code in the 500's and creates an alert with a threshold of 10
    app.alert("custom",conditions=[CustomMetricCondition("custom", metric_filter='severity=(ERROR OR CRITICAL OR ALERT OR EMERGENCY) httpRequest.status=(500 OR 501 OR 502 OR 503 OR 504)', value=10)])

Redis
^^^^^
.. code:: python

    app = Goblet()
    app.redis("redis-example")

When deploying a backend, the environment variables will automatically be updated to include the `REDIS_INSTANCE_NAME`, `REDIS_HOST` and `REDIS_PORT`. 
To further configure your Redis Instance within Goblet, specify the **`redis`** key in your `config.json`. 
You can reference `Redis Instance Resource <https://cloud.google.com/memorystore/docs/redis/reference/rest/v1/projects.locations.instances#Instance>`_ for more information on available fields.

VPC Connector
^^^^^^^^^^^^^
.. code:: python

    app = Goblet()
    app.vpcconnector("vpcconnector")

When deploying a backend, the vpc access configuration will be updated to include the specified vpc connector.
To further configure your VPC Connector within Goblet, specify the **`vpcconnector`** key in your `config.json`. 
You can reference `Connector Resource <https://cloud.google.com/vpc/docs/reference/vpcaccess/rest/v1/projects.locations.connectors#Connector>`_  for more information on available fields.

.. note::
    * In order to ensure proper configuration of the VPC Connector, the `ipCidrRange` key is required to be set within `vpcconnector` of your `config.json`.
