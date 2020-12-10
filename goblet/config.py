import json 
from goblet.utils import get_g_dir

class GConfig:
    def __init__(self, config=None):
        self.config = config or self.get_g_config()

    @staticmethod
    def get_g_config():
        try:
            with open(f'{get_g_dir()}/config.json') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def  __getattr__(self, name):
        attr = self.config.get(name)
        if attr:
            return attr

        return None

    def __setattr__(self, name, value):
        if name != "config":
            self.config[name] = value
        else:
            super(GConfig, self).__setattr__(name, value)

    def write(self):
        with open(f'{get_g_dir()}/config.json') as f:
            f.write(json.dumps(self.config))