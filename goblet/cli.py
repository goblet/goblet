from goblet.config import GConfig
import click
import os
import logging
import subprocess

from goblet.utils import get_goblet_app, create_goblet_dir
from goblet.deploy import Deployer
from goblet.client import Client, get_default_project
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
    """current goblet version"""
    click.echo(__version__)


@main.command()
@click.option('-p', '--project', 'project', envvar='GOOGLE_PROJECT')
@click.option('-l', '--location', 'location', envvar='GOOGLE_LOCATION', required=True)
@click.option('-s', '--stage', 'stage', envvar='STAGE')
@click.option('--skip-function', 'skip_function', is_flag=True)
@click.option('--only-function', 'only_function', is_flag=True)
@click.option('-f', '--force', 'force', is_flag=True)
def deploy(project, location, stage, skip_function, only_function, force):
    """
    You can set the project and location using environment variable GOOGLE_PROJECT and GOOGLE_LOCATION

    Note: Allowed GOOGLE_LOCATION values for API GATEWAY are: asia-east1, europe-west1, us-eastl1 and us-central1.

    Note: Make sure api-gateway, cloudfunctions, and storage are enabled in your project
    """
    try:
        _project = project or get_default_project()
        if not _project:
            click.echo("Project not found. Set --project flag or add to gcloud by using gcloud config set project PROJECT")
        os.environ["GOOGLE_PROJECT"] = _project
        os.environ["GOOGLE_LOCATION"] = location
        if stage:
            os.environ["STAGE"] = stage
        app = get_goblet_app()
        Deployer({"name": app.function_name}).deploy(app, skip_function=skip_function, only_function=only_function, force=force)

    except FileNotFoundError as not_found:
        click.echo(f"Missing {not_found.filename}. Make sure you are in the correct directoty and this file exists")


@main.command()
@click.option('-p', '--project', 'project', envvar='GOOGLE_PROJECT')
@click.option('-l', '--location', 'location', envvar='GOOGLE_LOCATION', required=True)
@click.option('-s', '--stage', 'stage', envvar='STAGE')
def destroy(project, location, stage):
    """
    Deletes all resources in gcp that are defined the current deployment
    """
    try:
        _project = project or get_default_project()
        if not _project:
            click.echo("Project not found. Set --project flag or add to gcloud by using gcloud config set project PROJECT")
        os.environ["GOOGLE_PROJECT"] = _project
        os.environ["GOOGLE_LOCATION"] = location
        if stage:
            os.environ["STAGE"] = stage
        app = get_goblet_app()
        Deployer({"name": app.function_name}).destroy(app)

    except FileNotFoundError as not_found:
        click.echo(f"Missing {not_found.filename}. Make sure you are in the correct directoty and this file exists")


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

    except FileNotFoundError as not_found:
        click.echo(f"Missing {not_found.filename}. Make sure you are in the correct directoty and this file exists")


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


@click.option('-s', '--stage', 'stage', envvar='STAGE')
@main.command()
def package(stage):
    """generates the goblet zipped package in .goblet folder"""
    try:
        if stage:
            os.environ["STAGE"] = stage
        app = get_goblet_app()
        Deployer({"name": app.function_name}).package()

    except FileNotFoundError as not_found:
        click.echo(f"Missing {not_found.filename}. Make sure you are in the correct directoty and this file exists")


@click.argument('name',)
@main.command()
def init(name):
    """Create new goblet app with files main.py, requirements.txt, and directory .goblet"""
    create_goblet_dir(name)
    click.echo("created .goblet/json.config")
    click.echo("created requirements.txt")
    click.echo("created main.py")
    click.echo("created README.md")


@main.command(name="logs")
@click.option('-p', '--project', 'project', envvar='GOOGLE_PROJECT', required=True)
@click.option('-l', '--location', 'location', envvar='GOOGLE_LOCATION', required=True)
@click.option('-s', '--stage', 'stage', envvar='STAGE')
def logs(project, location, stage):
    """Get logs from deployed cloudfunctions"""
    app = get_goblet_app()
    function_name = app.function_name
    if stage:
        function_name = f"{app.function_name}-{stage}"
    log_client = Client("logging", 'v2', calls='entries')
    
    log_filter = 'resource.type == "cloud_function"'
    log_filter += f' AND resource.labels.function_name == "{function_name}"'
    log_filter += f' AND resource.labels.region == "{location}"'
    log_filter += f' AND severity>=DEFAULT'

    log_request = {
       "resourceNames": [
           f"projects/{project}/"
        ],
        filter: log_filter
    }
    import pdb; pdb.set_trace()
    resp = log_client.execute("list", params={'body':log_request})
    for entry in resp["entries"]:
        click.echo(entry["payload"])


@main.group()
def stage():
    """view and create different environment stages"""
    pass


@stage.command(name="list")
def list_stages():
    config = GConfig.get_g_config()
    if not config.get("stages"):
        return click.echo("no stages found")
    click.echo(list(config["stages"].keys()))


@stage.command()
@click.argument('stage',)
def create(stage):
    """create a new stage in config.json"""
    config = GConfig()
    if config.stages and stage in config.stages:
        return click.echo(f"stage {stage} already exists")
    app = get_goblet_app()
    function_name = f"{app.function_name}-{stage}"
    if not config.stages:
        config.stages = {stage: {"function_name": function_name}}
    else:
        config.stages[stage] = {"function_name": function_name}
    config.write()
    click.echo(f"stage {stage} created in config.json with function name {function_name}")
