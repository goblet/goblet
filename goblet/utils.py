import os 

def get_app_from_module(m):
    from goblet import Goblet
    for obj in dir(m):
        if isinstance(getattr(m,obj), Goblet):
            return getattr(m,obj)

def get_g_dir():
    return f"{os.path.realpath('.')}/.goblet"
def get_dir():
    return os.path.realpath('.')