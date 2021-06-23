import os
import importlib.util
from contextlib import contextmanager
import json
from goblet.__version__ import __version__


@contextmanager
def add_to_path(p):
    import sys
    old_path = sys.path
    sys.path = sys.path[:]
    sys.path.insert(0, p)
    try:
        yield
    finally:
        sys.path = old_path


def checksum(fh, hasher, blocksize=65536):
    """Calculates checksum of file"""
    buf = fh.read(blocksize)
    while len(buf) > 0:
        hasher.update(buf)
        buf = fh.read(blocksize)
    return hasher.digest()


def get_app_from_module(m):
    from goblet import Goblet
    for obj in dir(m):
        if isinstance(getattr(m, obj), Goblet):
            return getattr(m, obj), obj


def get_goblet_app():
    """Look for main.py and return goblet app instance. Also sets the entrypoint for the app"""
    dir_path = os.path.realpath('.')
    spec = importlib.util.spec_from_file_location("main", f"{dir_path}/main.py")
    main = importlib.util.module_from_spec(spec)
    with add_to_path(dir_path):
        spec.loader.exec_module(main)
        app, app_name = get_app_from_module(main)
    setattr(app, "entrypoint", app_name)
    return app


def get_g_dir():
    """Gets the .goblet directory"""
    return f"{os.path.realpath('.')}/.goblet"


def get_dir():
    return os.path.realpath('.')


def create_goblet_dir(name):
    """Creates a new goblet directory with a sample main.py, requirements.txt, and config.json"""
    try:
        os.mkdir(get_g_dir())
    except FileExistsError:
        pass
    with open(f'{get_g_dir()}/config.json', 'w') as f:
        f.write(json.dumps({'cloudfunction': {}}, indent=4))
    with open('requirements.txt', 'w') as f:
        f.write(f'goblet-gcp=={__version__}')
    with open('main.py', 'w') as f:
        f.write(f"""
from goblet import Goblet, jsonify

app = Goblet(function_name="goblet-{name}", local="local")

@app.http()
def main(request):
    return jsonify(request.json)

# route
# @app.route('/hello')
# def home():
#     return jsonify("goodbye")

# schedule
# @app.schedule('5 * * * *')
# def scheduled_job():
#     return jsonify("success")

# pubsub topic
# @app.topic('test_topic')
# def topic(data):
#     app.log.info(data)
#     return
""")
    with open('README.md', 'w') as f:
        f.write(f"""
# goblet-{name}

autocreated by goblet

To test endpoints locally run `goblet local local`
To deploy cloudfunctions and other gcp resources defined in `main.py` run `goblet deploy`

To check out goblet documentation go to [docs](https://anovis.github.io/goblet/docs/build/html/index.html)
""")
