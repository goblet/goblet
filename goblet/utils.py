import os
import importlib.util
import collections.abc
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


def get_goblet_app(main_file="main.py"):
    """Look for main.py or main_file if defined and return goblet app instance."""
    dir_path = os.path.realpath(".")
    spec = importlib.util.spec_from_file_location("main", f"{dir_path}/{main_file}")
    main = importlib.util.module_from_spec(spec)
    with add_to_path(dir_path):
        spec.loader.exec_module(main)
        app, app_name = get_app_from_module(main)
    # setattr(app, "entrypoint", app_name)
    return app


def get_g_dir():
    """Gets the .goblet directory"""
    return f"{os.path.realpath('.')}/.goblet"


def get_dir():
    return os.path.realpath(".")


def nested_update(d, u):
    """
    Updates nested dictionary d with nested dictionary u
    """
    for k, v in u.items():
        if isinstance(v, collections.abc.Mapping):
            d[k] = nested_update(d.get(k, {}), v)
        else:
            d[k] = v
    return d
