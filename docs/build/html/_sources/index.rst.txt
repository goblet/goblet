.. goblet documentation master file, created by
   sphinx-quickstart on Thu Mar  5 10:18:25 2020.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to goblet's documentation!
==================================

Overview
----------

Goblet is a framework for writing serverless rest apis in python in google cloud. It allows you to quickly create and deploy python apis backed by `cloudfunctions`_. 

.. _cloudfunctions: https://cloud.google.com/functions/docs/reference/rest/v1/projects.locations.functions#CloudFunction

It provides:

* A command line tool for creating, deploying, and managing your api
* A decorator based API for integrating with GCP API Gateway, Storage, Cloudfunctions, PubSub, Scheduler, and other GCP services.
* Local environment for your api endpoints
* Dynamically generated openapispec
* Support for multiple stages

You can create Rest APIs:

.. code:: python

   from goblet import Goblet

   app = Goblet(function_name="goblet_example")

   @app.route('/home')
   def home():
      return {"hello": "world"}

   @app.route('/home/{id}', methods=["POST"], param_types={"name":"integer"})
   def post_example(id):
      return app.jsonify(id)


Once you've written your code, you just run goblet deploy and Goblet takes care of deploying your app.

.. code::

   $ goblet deploy
   ...
   https://api.uc.gateway.dev

   $ curl https://api.uc.gateway.dev/home
   {"hello": "world"}

Installation
------------

To install goblet, open an interactive shell and run:

.. code::

    pip install goblet-gcp

You will also need to install `gcloud cli`_ for authentication

.. note:: 
   
   Make sure to have the correct services enabled in your gcp project
   `api-gateway`, `cloudfunctions`, `storage`

.. note::

    Goblet requires python version 3.7 or higher.

.. _gcloud cli: https://cloud.google.com/sdk/docs/install

Quickstart
-----------

.. toctree::
   :maxdepth: 2
   
   quickstart

Topics
----------

.. toctree::
   :maxdepth: 2

   topics

Resources
----------

.. toctree::
   :maxdepth: 2

   resources

Backends
----------

.. toctree::
   :maxdepth: 2

   backends

Infrastructures
---------------

.. toctree::
   :maxdepth: 2

   infrastructures

Blogs
--------

.. toctree::
   :maxdepth: 2

   blogs

Integrations
------------

.. toctree::
   :maxdepth: 2

   integrations

Examples
--------

.. toctree::
   :maxdepth: 2

   examples

