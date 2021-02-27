import json
from goblet.utils import get_g_dir
import os


class GConfig:
    def __init__(self, config=None, stage=None):
        self.config = config or self.get_g_config()
        self.stage = stage or os.environ.get("STAGE")
        self.validate()
        if self.stage:
            self.config.update(self.config.get("stages", {}).get(self.stage, {}))

    @staticmethod
    def get_g_config():
        try:
            with open(f'{get_g_dir()}/config.json') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def __getattr__(self, name):
        attr = self.config.get(name)
        if attr:
            return attr
        if os.environ.get(name):
            return os.environ.get(name)

        return None

    def __setattr__(self, name, value):
        if name not in ["config", "stage"]:
            self.config[name] = value
        else:
            super(GConfig, self).__setattr__(name, value)

    def write(self):
        with open(f'{get_g_dir()}/config.json', 'w') as f:
            f.write(json.dumps(self.config, indent=4))

    def validate(self):
        if self.stage and self.stage not in self.config.get("stages"):
            raise ValueError(f"stage {self.stage} not found in config")
        for stage in self.config.get("stages", {}):
            if "function_name" not in self.config["stages"][stage]:
                raise ValueError(f"function_name key missing for stage {stage}")
