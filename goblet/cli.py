from goblet.config import GConfig
import click
import os
import logging
import subprocess
import json
import requests
import sys

from goblet.utils import get_g_dir, get_goblet_app
from goblet.write_files import create_goblet_dir
from goblet.client import get_default_project
from goblet.__version__ import __version__

logging.basicConfig()


@click.group()
def main():
    pass


@main.command()
def help():
    click.echo(
        "Use goblet --help. You can also view the full docs for goblet at https://goblet.github.io/goblet/docs/build/html/index.html"
    )


@main.command()
def version():
    """current goblet version"""
    click.echo(__version__)


@main.command()
@click.option("-p", "--project", "project", envvar="GOOGLE_PROJECT")
@click.option("-l", "--location", "location", envvar="GOOGLE_LOCATION", required=True)
@click.option("-s", "--stage", "stage", envvar="STAGE")
@click.option("--skip-resources", "skip_resources", is_flag=True)
@click.option("--skip-backend", "skip_backend", is_flag=True)
@click.option("--skip-infra", "skip_infra", is_flag=True)
@click.option("--config-from-json-string", "config")
@click.option("-f", "--force", "force", is_flag=True)
@click.option("--write-config", "write_config", is_flag=True)
def deploy(
    project,
    location,
    stage,
    skip_resources,
    skip_backend,
    skip_infra,
    config,
    force,
    write_config,
):
    """
    You can set the project and location using environment variable GOOGLE_PROJECT and GOOGLE_LOCATION

    Note: Allowed GOOGLE_LOCATION values for API GATEWAY are: asia-east1, europe-west1, us-eastl1 and us-central1.

    Note: Make sure api-gateway, cloudfunctions, and storage are enabled in your project
    """
    os.environ["X-GOBLET-DEPLOY"] = "true"
    try:
        _project = project or get_default_project()
        if not _project:
            click.echo(
                "Project not found. Set --project flag or add to gcloud by using gcloud config set project PROJECT"
            )
        os.environ["GOOGLE_PROJECT"] = _project
        os.environ["GOOGLE_LOCATION"] = location
        if stage:
            os.environ["STAGE"] = stage

        # import config from string
        imported_config = {}
        if config:
            imported_config = json.loads(config)

        # get goblet config
        goblet_config = GConfig(imported_config)

        # set deploy env vars
        if goblet_config.deploy:
            for key, value in goblet_config.deploy.get(
                "environmentVariables", []
            ).items():
                os.environ[key] = value

        app = get_goblet_app(goblet_config.main_file or "main.py")
        app.deploy(
            skip_resources,
            skip_backend,
            skip_infra,
            config=goblet_config.config,
            force=force,
            stage=stage,
            write_config=write_config,
        )

    except FileNotFoundError as not_found:
        click.echo(
            f"Missing {not_found.filename}. Make sure you are in the correct directory and this file exists"
        )
        sys.exit(1)


@main.command()
@click.option("-p", "--project", "project", envvar="GOOGLE_PROJECT")
@click.option("-l", "--location", "location", envvar="GOOGLE_LOCATION", required=True)
@click.option("-s", "--stage", "stage", envvar="STAGE")
@click.option("-a", "--all", "all", is_flag=True)
@click.option("--skip-infra", "skip_infra", is_flag=True)
def destroy(project, location, stage, all, skip_infra):
    """
    Deletes all resources in gcp that are defined the current deployment

    The --all flag removes cloudfunction artifacts in cloud storage as well
    """
    os.environ["X-GOBLET-DEPLOY"] = "true"
    try:
        _project = project or get_default_project()
        if not _project:
            click.echo(
                "Project not found. Set --project flag or add to gcloud by using gcloud config set project PROJECT"
            )
        os.environ["GOOGLE_PROJECT"] = _project
        os.environ["GOOGLE_LOCATION"] = location
        if stage:
            os.environ["STAGE"] = stage

        # get goblet config
        goblet_config = GConfig()

        # set deploy env vars
        if goblet_config.deploy:
            for key, value in goblet_config.deploy.get(
                "environmentVariables", []
            ).items():
                os.environ[key] = value

        app = get_goblet_app(goblet_config.main_file or "main.py")
        app.destroy(all, skip_infra)

    except FileNotFoundError as not_found:
        click.echo(
            f"Missing {not_found.filename}. Make sure you are in the correct directory and this file exists"
        )
        sys.exit(1)


@main.command()
@click.option("-p", "--project", "project", envvar="GOOGLE_PROJECT")
@click.option("-l", "--location", "location", envvar="GOOGLE_LOCATION", required=True)
@click.option("-s", "--stage", "stage", envvar="STAGE")
@click.option("-d", "--dryrun", "dryrun", is_flag=True)
def sync(project, location, stage, dryrun):
    """
    Syncs resources that are deployed with current app configuration. This command will delete resources based on naming
    convention that are no longer in the app configuration.

    Use --dryrun flag to see what resources are flagged as being deleted.
    """
    os.environ["X-GOBLET-DEPLOY"] = "true"
    try:
        _project = project or get_default_project()
        if not _project:
            click.echo(
                "Project not found. Set --project flag or add to gcloud by using gcloud config set project PROJECT"
            )
        os.environ["GOOGLE_PROJECT"] = _project
        os.environ["GOOGLE_LOCATION"] = location
        if stage:
            os.environ["STAGE"] = stage
        app = get_goblet_app(GConfig().main_file or "main.py")
        app.sync(dryrun)

    except FileNotFoundError as not_found:
        click.echo(
            f"Missing {not_found.filename}. Make sure you are in the correct directory and this file exists"
        )
        sys.exit(1)


@main.command()
@click.argument("cloudfunction")
@click.option("-s", "--stage", "stage", envvar="STAGE")
@click.option("-v", "--version", "version", envvar="VERSION", type=click.Choice("3"))
def openapi(cloudfunction, stage, version):
    """
    You can find the generated openapi spec in /.goblet folder.

    The cloudfunction argument sets the correct x-google-backend address in the openapi spec.
    """
    os.environ["X-GOBLET-DEPLOY"] = "true"
    if stage:
        os.environ["STAGE"] = stage
    try:
        app = get_goblet_app(GConfig().main_file or "main.py")
        app.handlers["route"].generate_openapi_spec(cloudfunction)
    except FileNotFoundError as not_found:
        click.echo(
            f"Missing {not_found.filename}. Make sure you are in the correct directory and this file exists"
        )
        sys.exit(1)

    if version:
        with open(f"{get_g_dir()}/{app.function_name}_openapi_spec.yml", "r") as f:
            data = f.read()
        headers = {
            "accept": "application/yaml",
            "Content-Type": "application/yaml",
        }
        response = requests.post(
            "https://converter.swagger.io/api/convert", headers=headers, data=data
        )
        with open(f"{get_g_dir()}/{app.function_name}_openapi_spec_3.yml", "w") as f:
            f.write(response.text)


@main.command()
@click.argument("local_arg", default="local")
@click.option("-s", "--stage", "stage", envvar="STAGE")
@click.option("-p", "--port", "port", envvar="PORT", default=8080)
@click.option("--set-env", "set_env", is_flag=True)
def local(local_arg, stage, port, set_env):
    """
    Requires the local argument to be set in the Goblet class. The default is local.

    For example in this case you would use local_function

    Goblet("test_function",local="local_function")
    """
    os.environ["X_GOBLET_LOCAL"] = "true"
    try:
        if stage:
            os.environ["STAGE"] = stage
        config = GConfig()
        source = config.main_file or "main.py"
        if set_env:
            app = get_goblet_app(source)
            env_dict = app.backend.get_environment_vars()
            for k, v in env_dict.items():
                os.environ[k] = v
        subprocess.check_output(
            [
                "functions-framework",
                f"--target={local_arg}",
                "--debug",
                f"--source={source}",
                f"--port={port}",
            ]
        )
    except subprocess.CalledProcessError:
        click.echo(
            "Incorrect argument. Make sure you set the local param in your Goblet class and that it matches the arg used in goblet local"
        )


@click.option("-s", "--stage", "stage", envvar="STAGE")
@main.command()
def package(stage):
    """generates the goblet zipped package in .goblet folder"""
    os.environ["X-GOBLET-DEPLOY"] = "true"
    try:
        if stage:
            os.environ["STAGE"] = stage
        app = get_goblet_app(GConfig().main_file or "main.py")
        app.package()

    except FileNotFoundError as not_found:
        click.echo(
            f"Missing {not_found.filename}. Make sure you are in the correct directory and this file exists"
        )
        sys.exit(1)


@click.argument(
    "name",
)
@main.command()
def init(name):
    """Create new goblet app with files main.py, requirements.txt, and directory .goblet"""
    create_goblet_dir(name)
    click.echo("created .goblet/config.json")
    click.echo("created requirements.txt")
    click.echo("created main.py")
    click.echo("created README.md")


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
@click.argument(
    "stage",
)
def create(stage):
    """create a new stage in config.json"""
    os.environ["X-GOBLET-DEPLOY"] = "true"
    config = GConfig()
    if config.stages and stage in config.stages:
        return click.echo(f"stage {stage} already exists")
    app = get_goblet_app(GConfig().main_file or "main.py")
    function_name = f"{app.function_name}-{stage}"
    if not config.stages:
        config.stages = {stage: {"function_name": function_name}}
    else:
        config.stages[stage] = {"function_name": function_name}
    config.write()
    click.echo(
        f"stage {stage} created in config.json with function name {function_name}"
    )


@main.group()
def job():
    """run cloudrun jobs"""
    pass


@job.command(name="run")
@click.argument(
    "name",
)
@click.argument("task_id", envvar="CLOUD_RUN_TASK_INDEX", default="0")
def run_job(name, task_id):
    """
    Run a Cloudrun Job in local environment.
    """
    os.environ["CLOUD_RUN_TASK_INDEX"] = task_id
    try:
        app = get_goblet_app(GConfig().main_file or "main.py")
        app(name, int(task_id))

    except FileNotFoundError as not_found:
        click.echo(
            f"Missing {not_found.filename}. Make sure you are in the correct directory and this file exists"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()  # pylint: disable=no-value-for-parameter
