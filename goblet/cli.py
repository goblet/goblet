import click
import os
import importlib.util

from goblet.utils import get_app_from_module
from goblet.deploy import Deployer

@click.group()
def main():
    pass

@main.command()
def help():
    click.echo('Help coming soon...see docs for now')

@main.command()
def deploy():
    try:
        app = get_goblet_app()
        Deployer().deploy(app)

    except FileNotFoundError:
        click.echo("Missing main.py. This is the required entrypoint for google cloud functions")

@main.command()
def package():
    try:
        app = get_goblet_app()
        Deployer().package(app)

    except FileNotFoundError:
        click.echo("Missing main.py. This is the required entrypoint for google cloud functions")


def get_goblet_app():
        # load main
    dir_path = os.path.realpath('.')
    spec = importlib.util.spec_from_file_location("main", f"{dir_path}/main.py")
    main = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(main)
    app = get_app_from_module(main)
    return app