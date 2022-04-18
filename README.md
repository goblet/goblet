# GOBLET

![PyPI](https://img.shields.io/pypi/v/goblet-gcp?color=blue&style=plastic)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/goblet-gcp?style=plastic)
![Tests](https://github.com/anovis/goblet/actions/workflows/main.yml/badge.svg)
[![codecov](https://codecov.io/gh/anovis/goblet/branch/master/graph/badge.svg?token=g8TL6Sc0P5)](https://codecov.io/gh/anovis/goblet)

Goblet is a framework for writing serverless rest apis in python in google cloud. It allows you to quickly create and deploy python apis backed by [cloudfunctions](https://cloud.google.com/functions). 

It provides:

* A command line tool for creating, deploying, and managing your api
* A decorator based API for integrating with GCP API Gateway, Storage, Cloudfunctions, PubSub, Scheduler, and other GCP services.
* Local environment for your api endpoints
* Dynamically generated openapispec
* Support for multiple stages

You can create Rest APIs:

```python
from goblet import Goblet, jsonify, goblet_entrypoint

app = Goblet(function_name="goblet_example")
goblet_entrypoint(app)

@app.route('/home')
def home():
    return {"hello": "world"}

@app.route('/home/{id}', methods=["POST"])
def post_example(id: int) -> List[int]:
    return jsonify([id])
```

Once you've written your code, you just run goblet deploy and Goblet takes care of deploying your app.

```sh
$ goblet deploy -l us-central1
...
https://api.uc.gateway.dev

$ curl https://api.uc.gateway.dev/home
{"hello": "world"}
```

> Note: Due to breaking changes in Cloudfunctions you will need to wrap your goblet class in a function. See [issue #88](https://github.com/anovis/goblet/issues/88). In the latest goblet version (0.5.0) there is a helper function `goblet_entrypoint` that can be used as well. 

> `goblet_entrypoint(app)`

## Resources Supported

#### Backends
* cloudfunction
* cloudrun

#### Routing
* api gateway
* http

#### Triggering
* pubsub
* scheduler
* storage
* eventarc

## Installation

To install goblet, open an interactive shell and run:

```pip install goblet-gcp```

Make sure to have the correct services enabled in your gcp project depending on what you want to deploy

`api-gateway`, `cloudfunctions`, `storage`, `pubsub`, `scheduler`

You will also need to install [gcloud cli](https://cloud.google.com/sdk/docs/install) for authentication

## QuickStart

In this tutorial, you'll use the goblet command line utility to create and deploy a basic REST API. This quickstart uses Python 3.7. You can find the latest versions of python on the Python download page.

To install Goblet, we'll first create and activate a virtual environment in python3.7:

```sh
$ python3 --version
Python 3.7.3
$ python3 -m venv venv37
$ . venv37/bin/activate
```

Next we'll install Goblet using pip:

```sh
python3 -m pip install goblet-gcp
```

You can verify you have goblet installed by running:

```sh
$ goblet --help
Usage: goblet [OPTIONS] COMMAND [ARGS]...
...
```

### Credentials

Before you can deploy an application, be sure you have credentials configured. You should run `gcloud auth application-default login` and sign in to the desired project.

When setting the defaut location note that api-gateway is only available in `asia-east1`, `europe-west1`, `us-east-1` and `us-central1`.

### Creating Your Project

create your project directory, which should include an main.py and a requirements.txt. Make sure requirements.txt includes `goblet-gcp`

```sh
$ ls -la
drwxr-xr-x   .goblet
-rw-r--r--   main.py
-rw-r--r--   requirements.txt
```

You can ignore the .goblet directory for now, the two main files we'll focus on is app.py and requirements.txt.

Let's take a look at the main.py file:

```python
from goblet import Goblet, goblet_entrypoint

app = Goblet(function_name="goblet_example")
goblet_entrypoint(app)

@app.route('/home')
def home():
    return {"hello": "world"}
```

This app will deploy an api with endpoint `/home`.

### Running Locally

Running your functions locally for testing and debugging is easy to do with goblet.

```python
from goblet import Goblet

app = Goblet(function_name="goblet_example")
goblet_entrypoint(app)

@app.route('/home')
def home():
    return {"hello": "world"}
```

Then run `goblet local`
Now you can hit your functions endpoint at `localhost:8080` with your routes. For example `localhost:8080/home`

### Deploying

Let's deploy this app. Make sure you're in the app directory and run goblet deploy making sure to specify the desired location:

```sh
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

```sh
$ curl https://goblet-example-yol8sbt.uc.gateway.dev/home
{"hello": "world"}
```

Try making a change to the returned dictionary from the home() function. You can then redeploy your changes by running `golet deploy`.

### Next Steps

You've now created your first app using goblet. You can make modifications to your main.py file and rerun goblet deploy to redeploy your changes.

At this point, there are several next steps you can take.

Docs - [Goblet Documentation](https://anovis.github.io/goblet/docs/build/html/index.html)

If you're done experimenting with Goblet and you'd like to cleanup, you can use the `goblet destroy` command making sure to specify the desired location, and Goblet will delete all the resources it created when running the goblet deploy command.

```sh
$ goblet destroy -l us-central1
INFO:goblet.deployer:destroying api gateway......
INFO:goblet.deployer:api configs destroying....
INFO:goblet.deployer:apis successfully destroyed......
INFO:goblet.deployer:deleting google cloudfunction......
INFO:goblet.deployer:deleting storage bucket......
```

## Docs

[Goblet Documentation](https://anovis.github.io/goblet/docs/build/html/index.html)

## Blog Posts

[Building Python Serverless Applications on GCP](https://austennovis.medium.com/building-python-serverless-applications-on-gcp-141a806eb7a5)

[Serverless APIs made simple on GCP with Goblet backed by Cloud Functions and Cloud Run](https://engineering.premise.com/serverless-apis-made-simple-on-gcp-with-goblet-backed-by-cloud-functions-and-cloud-run-730db2da04ba)

[Tutorial: Publishing GitHub Findings to Security Command Center](https://engineering.premise.com/tutorial-publishing-github-findings-to-security-command-center-2d1749f530bc)

[Tutorial: Cost Spike Alerting](https://engineering.premise.com/tutorial-cost-spike-alerting-for-google-cloud-platform-gcp-46fd26ae3f6a)

[Tutorial: Setting Up Approval Processes with Slack Apps](https://engineering.premise.com/tutorial-setting-up-approval-processes-with-slack-apps-d325aee31763)


## Examples

[Goblet Examples](https://github.com/anovis/goblet/blob/master/examples/main.py)

## Issues

Please file any issues, bugs or feature requests as an issue on our [GitHub](https://github.com/anovis/goblet/issues) page.

## Github Action

[Goblet Github Action](https://github.com/marketplace/actions/goblet-deploy)

## Roadmap

 &#9745; Integration Tests \
 &#9745; [Api Gateway Auth](https://cloud.google.com/api-gateway/docs/authenticate-service-account) \
 &#9745; Configuration Options (function names, ...) \
 &#9745; Use checksum for updates \
 &#9745; Cloudrun Backend \
 &#9745; [Scheduler](https://cloud.google.com/scheduler) trigger \
 &#9745; [Pub Sub](https://cloud.google.com/pubsub/docs/overview) trigger \
 &#9745; [Cloud Storage](https://cloud.google.com/functions/docs/calling/storage) trigger \
 &#9744; [Firestore]( https://cloud.google.com/functions/docs/calling/cloud-firestore) trigger \
 &#9744; [Firebase](https://cloud.google.com/functions/docs/calling/realtime-database) trigger \
 &#9744; [Cloud Tasks](https://cloud.google.com/tasks/docs/creating-http-target-tasks) trigger \
 &#9744; [Cloud Endpoints](https://cloud.google.com/endpoints/docs/openapi/get-started-cloud-functions) trigger \
 &#9745; [EventArc](https://cloud.google.com/eventarc/docs) trigger

## Want to Contribute

If you would like to contribute to the library (e.g. by improving the documentation, solving a bug or adding a cool new feature) submit a [pull request](https://github.com/anovis/goblet/pulls).

## Want to Support

<!-- markdownlint-disable MD033 -->
<a href="https://www.buymeacoffee.com/austennovis" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-blue.png" alt="Buy Me A Coffee" height="41" width="174"></a>
<!-- markdownlint-disable MD033 -->

___

Based on [chalice](https://github.com/aws/chalice)
