import os
import importlib.util
from contextlib import contextmanager

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

def get_app_from_module(m):
    from goblet import Goblet
    for obj in dir(m):
        if isinstance(getattr(m,obj), Goblet):
            return getattr(m,obj), obj

def get_goblet_app():
    # looks for main.py and gets goblet app
    dir_path = os.path.realpath('.')
    spec = importlib.util.spec_from_file_location("main", f"{dir_path}/main.py")
    main = importlib.util.module_from_spec(spec)
    with add_to_path(dir_path):
        spec.loader.exec_module(main)
        app, app_name = get_app_from_module(main)
    setattr(app, "entrypoint", app_name)
    return app

def get_g_dir():
    return f"{os.path.realpath('.')}/.goblet"

def get_dir():
    return os.path.realpath('.')