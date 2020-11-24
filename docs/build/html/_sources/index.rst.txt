.. goblet documentation master file, created by
   sphinx-quickstart on Thu Mar  5 10:18:25 2020.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to goblet's documentation!
==================================

Overview
----------

Goblet is a framework for writing serverless apps in python in google cloud. It allows you to quickly create and deploy applications that use [cloudfunctions](https://cloud.google.com/functions). It provides:

* A command line tool for creating, deploying, and managing your app
* A decorator based API for integrating with GCP API Gateway (beta), Storage, Cloudfunctions, PubSub, Scheduler, and other GCP services.
* Unified logging and error handling with stackdriver
* Utitilies to help with tracking events through in a pubsub pipeline

You can create Rest APIs:

.. code:: python

   from goblet import Goblet

   app = Goblet(function_name="goblet_example",region='us-central-1')

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

    pip install goblet-gcs
<<<<<<< HEAD
=======


.. note:: 
   
   Make sure to have the correct services enabled in your gcp project
   `api-gateway`, `cloudfunctions`, `storage`
>>>>>>> fea4d8690498114781025eaea73e18a4e4371285

.. note::

    Goblet requires python version 3.7 or higher.


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


