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
    click.echo('Help coming soon...see docs for now')

@main.command()
@click.option('-p', '--project', 'project', envvar='GOOGLE_PROJECT')
@click.option('-l', '--location', 'location', envvar='GOOGLE_LOCATION')
def deploy(project, location):
    try:
        os.environ["GOOGLE_PROJECT"]=project
        os.environ["GOOGLE_LOCATION"]=location
        app = get_goblet_app()
        Deployer().deploy(app)

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
        Deployer().destroy(app)

    except FileNotFoundError:
        click.echo("Missing main.py. This is the required entrypoint for google cloud functions")

@main.command()
def package():
    try:
        app = get_goblet_app()
        Deployer().package(app)

    except FileNotFoundError:
        click.echo("Missing main.py. This is the required entrypoint for google cloud functions")
