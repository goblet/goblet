import click
import os
import logging
import subprocess

from goblet.utils import get_goblet_app
from goblet.deploy import Deployer
from goblet.__version__ import __version__

logging.basicConfig()


@click.group()
def main():
    pass


@main.command()
def help():
    click.echo('Use goblet --help. You can also view the full docs for goblet at https://anovis.github.io/goblet/docs/build/html/index.html')


@main.command()
def version():
    click.echo(__version__)


@main.command()
@click.option('-p', '--project', 'project', envvar='GOOGLE_PROJECT', required=True)
@click.option('-l', '--location', 'location', envvar='GOOGLE_LOCATION', required=True)
@click.option('--skip-function', 'skip_function', is_flag=True)
@click.option('--only-function', 'only_function', is_flag=True)
def deploy(project, location, skip_function, only_function):
    """
    You can set the project and location using environment variable GOOGLE_PROJECT and GOOGLE_LOCATION

    Note: Allowed GOOGLE_LOCATION values for API GATEWATy Beta are: asia-east1, europe-west1, and us-central1.

    Note: Make sure api-gateway, cloudfunctions, and storage are enabled in your project
    """
    try:
        os.environ["GOOGLE_PROJECT"] = project
        os.environ["GOOGLE_LOCATION"] = location
        app = get_goblet_app()
        Deployer({"name": app.function_name}).deploy(app, skip_function=skip_function, only_function=only_function)

    except FileNotFoundError:
        click.echo("Missing main.py. This is the required entrypoint for google cloud functions")


@main.command()
@click.option('-p', '--project', 'project', envvar='GOOGLE_PROJECT')
@click.option('-l', '--location', 'location', envvar='GOOGLE_LOCATION')
def destroy(project, location):
    try:
        os.environ["GOOGLE_PROJECT"] = project
        os.environ["GOOGLE_LOCATION"] = location
        app = get_goblet_app()
        Deployer({"name": app.function_name}).destroy(app)

    except FileNotFoundError:
        click.echo("Missing main.py. This is the required entrypoint for google cloud functions")


@main.command()
@click.argument('cloudfunction')
def openapi(cloudfunction):
    """
    You can find the generated openapi spec in /.goblet folder.

    The cloudfunction argument sets the correct x-google-backend address in the openapi spec.
    """
    try:
        app = get_goblet_app()
        app.handlers["route"].generate_openapi_spec(cloudfunction)

    except FileNotFoundError:
        click.echo("Missing main.py. This is the required entrypoint for google cloud functions")


@main.command()
@click.argument('local_arg',)
def local(local_arg):
    """
    Requires the local argument to be set in the Goblet class.

    For example in this case you would use local_function

    Goblet("test_function",local="local_function")
    """
    try:
        subprocess.check_output(["functions-framework", f"--target={local_arg}", "--debug"])
    except subprocess.CalledProcessError:
        click.echo("Incorrect argument. Make sure you set the local param in your Goblet class and that it matches the arg used in goblet local")


@main.command()
def package():
    try:
        app = get_goblet_app()
        Deployer({"name": app.function_name}).package(app)

    except FileNotFoundError:
        click.echo("Missing main.py. This is the required entrypoint for google cloud functions")
