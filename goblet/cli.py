import click
import os 
import logging 

from goblet.utils import get_goblet_app
from goblet.deploy import Deployer

logging.basicConfig()

@click.group()
def main():
    pass

@main.command()
def help():
    click.echo('Use goblet --help. You can also view the full docs for goblet at https://anovis.github.io/goblet/docs/build/html/index.html')

@main.command()
@click.option('-p', '--project', 'project', envvar='GOOGLE_PROJECT', required=True)
@click.option('-l', '--location', 'location', envvar='GOOGLE_LOCATION', required=True)
@click.option('--skip-function','skip_function', is_flag=True)
@click.option('--only-function','only_function', is_flag=True)
def deploy(project, location,skip_function, only_function):
    """
    You can set the project and location using environment variable GOOGLE_PROJECT and GOOGLE_LOCATION
    
    Note: Allowed GOOGLE_LOCATION values for API GATEWATy Beta are: asia-east1, europe-west1, and us-central1.

    Note: Make sure api-gateway, cloudfunctions, and storage are enabled in your project
    """
    try:
        os.environ["GOOGLE_PROJECT"]=project
        os.environ["GOOGLE_LOCATION"]=location
        app = get_goblet_app()
        Deployer({"name":app.function_name}).deploy(app, skip_function=skip_function, only_function=only_function)

    except FileNotFoundError:
        click.echo("Missing main.py. This is the required entrypoint for google cloud functions")

@main.command()
@click.option('-p', '--project', 'project', envvar='GOOGLE_PROJECT')
@click.option('-l', '--location', 'location', envvar='GOOGLE_LOCATION')
def destroy(project, location):
    try:
        os.environ["GOOGLE_PROJECT"]=project
        os.environ["GOOGLE_LOCATION"]=location
        app = get_goblet_app()
        Deployer({"name":app.function_name}).destroy(app)

    except FileNotFoundError:
        click.echo("Missing main.py. This is the required entrypoint for google cloud functions")

@main.command()
@click.option('-p', '--project', 'project', envvar='GOOGLE_PROJECT')
@click.option('-l', '--location', 'location', envvar='GOOGLE_LOCATION')
@click.argument('cloudfunction')
def openapi(project, location, cloudfunction):
    """
    You can find the generated openapi spec in /.goblet folder. 

    The cloudfunction argument sets the correct x-google-backend address in the openapi spec.
    """
    try:
        os.environ["GOOGLE_PROJECT"]=project
        os.environ["GOOGLE_LOCATION"]=location
        app = get_goblet_app()
        app.handlers["route"].generate_openapi_spec(cloudfunction)

    except FileNotFoundError:
        click.echo("Missing main.py. This is the required entrypoint for google cloud functions")

@main.command()
def package():
    try:
        app = get_goblet_app()
        Deployer({"name":app.function_name}).package(app)

    except FileNotFoundError:
        click.echo("Missing main.py. This is the required entrypoint for google cloud functions")
