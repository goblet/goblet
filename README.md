# GOBLET

![PyPI](https://img.shields.io/pypi/v/goblet-gcp?color=blue&style=plastic)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/goblet-gcp?style=plastic)

Goblet is a framework for writing serverless apps in python in google cloud. It allows you to quickly create and deploy applications that use [cloudfunctions](https://cloud.google.com/functions). It provides:

* A command line tool for creating, deploying, and managing your app
* A decorator based API for integrating with GCP API Gateway (beta), Storage, Cloudfunctions, PubSub, Scheduler, and other GCP services.
* Local environment for your api endpoints

You can create Rest APIs:

```python
from goblet import Goblet

app = Goblet(function_name="goblet_example",region='us-central-1')

@app.route('/home')
def home():
    return {"hello": "world"}

@app.route('/home/{id}', methods=["POST"], param_types={"name":"integer"})
def post_example(id):
    return app.jsonify(id)
```

Once you've written your code, you just run goblet deploy and Goblet takes care of deploying your app.

```sh
$ goblet deploy
...
https://api.uc.gateway.dev

$ curl https://api.uc.gateway.dev/home
{"hello": "world"}
```

## Installation

To install goblet, open an interactive shell and run:

```pip install goblet-gcp```

Make sure to have the correct services enabled in your gcp project

`api-gateway`, `cloudfunctions`, `storage`

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

Before you can deploy an application, be sure you have credentials configured. You should run `gcloud auth login` and sign in to the desired project.

When setting the defaut location note tha api-gateway is only available in `asia-east1`, `europe-west1`, and `us-central1`.

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
from goblet import Goblet

app = Goblet(function_name="goblet_example",region='us-central-1')

@app.route('/home')
def index():
    return {"hello": "world"}
```

This app with deploy an api with endpoint `/home`.

### Running Locally

Running your functions locally for testing and debugging is easy to do with goblet. First set a local param in the goblet class

```python
from goblet import Goblet

app = Goblet(function_name="goblet_example",region='us-central-1', local='test')

```

Then run `goblet local test` and replace test with whatever variable you decide to use.
Now you can hit your functions endpoint at `localhost:8080` with your routes.

### Deploying

Let's deploy this app. Make sure you're in the app directory and run goblet deploy:

```sh
$ goblet deploy
INFO:goblet.deployer:zipping function......
INFO:goblet.deployer:uploading function zip to gs......
INFO:goblet.deployer:creating google function......
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

If you're done experimenting with Goblet and you'd like to cleanup, you can use the `goblet destroy` command, and Goblet will delete all the resources it created when running the goblet deploy command.

```sh
$ goblet destroy
INFO:goblet.deployer:destroying api gateway......
INFO:goblet.deployer:api configs destroying....
INFO:goblet.deployer:apis successfully destroyed......
INFO:goblet.deployer:deleting google cloudfunction......
INFO:goblet.deployer:deleting storage bucket......
```

## Docs

[Goblet Documentation](https://anovis.github.io/goblet/docs/build/html/index.html)

## Issues

Please file any issues, bugs or feature requests as an issue on our [GitHub](https://github.com/anovis/goblet/issues) page.

## Roadmap

&#9744; Tests \
 &#9745; [Api Gateway Auth](https://cloud.google.com/api-gateway/docs/authenticate-service-account) \
 &#9745; Configuration Options (function names, ...)\
 &#9744; Cleanup gcp buckets\
 &#9744; Generate [Openapi](https://github.com/OpenAPITools/openapi-generator)  clients \
 &#9744; User generated dataclasses for openapi spec \
 &#9745; [Scheduler](https://cloud.google.com/scheduler) trigger \
 &#9744; [Pub Sub](https://cloud.google.com/pubsub/docs/overview) trigger

## Want to contribute

If you would like to contribute to the library (e.g. by improving the documentation, solving a bug or adding a cool new feature) submit a [pull request](https://github.com/anovis/goblet/pulls).

___

Based on [chalice](https://github.com/aws/chalice)
