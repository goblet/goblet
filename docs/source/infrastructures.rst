================
Infrastructure
================

You can now provision infrastructure within your Goblet code.

VPC Connector
^^^^^^^^^^^^^
.. code:: python

    app = Goblet()
    app.redis("vpcconn-example")

.. note::
    * In order to ensure proper configuration of the VPC Connector, the `ipCidrRange` key is required to be set within the config.json

When deploying a backend, the vpc access configuration will be updated to include the specified vpc connector.
To further configure your VPC Connector within the goblet config you can reference `Connector Resource <https://cloud.google.com/vpc/docs/reference/vpcaccess/rest/v1/projects.locations.connectors#Connector>`_

Redis
^^^^^
.. code:: python

    app = Goblet()
    app.redis("redis-example")

When deploying a backend, the environment variables will automatically be updated to include the `REDIS_INSTANCE_NAME`, `REDIS_HOST` and `REDIS_PORT`.
To further configure your Redis Instance within the goblet config you can reference `Redis Instance Resource <https://cloud.google.com/memorystore/docs/redis/reference/rest/v1/projects.locations.instances#Instance>`_