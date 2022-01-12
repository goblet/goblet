import json
from goblet.utils import get_g_dir, nested_update
import os
import logging

log = logging.getLogger("goblet.config")
log.setLevel(logging.INFO)


class GConfig:
    """Config class used to get variables from config.json or from the environment. If stage is set as an environment level
    if will parse the corresponding section in config.json and return those config values"""

    def __init__(self, config=None, stage=None):
        self.config = self.get_g_config()
        if config:
            self.config = nested_update(self.config, config)
        self.stage = stage or os.environ.get("STAGE")
        self.validate()
        if self.stage:
            self.config = nested_update(
                self.config, self.config.get("stages", {}).get(self.stage, {})
            )

    @staticmethod
    def get_g_config():
        try:
            with open(f"{get_g_dir()}/config.json") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
        except json.decoder.JSONDecodeError:
            log.info(
                "JSONDecodeError. config.json is not valid. Returning empty config"
            )
            return {}

    def __getattr__(self, name):
        if os.environ.get(name):
            return os.environ.get(name)
        attr = self.config.get(name)
        if attr:
            return attr
        return None

    def __setattr__(self, name, value):
        if name not in ["config", "stage"]:
            self.config[name] = value
        else:
            super(GConfig, self).__setattr__(name, value)

    def write(self):
        with open(f"{get_g_dir()}/config.json", "w") as f:
            f.write(json.dumps(self.config, indent=4))

    def validate(self):
        if self.stage and self.stage not in self.config.get("stages"):
            raise ValueError(f"stage {self.stage} not found in config")
        for stage in self.config.get("stages", {}):
            if "function_name" not in self.config["stages"][stage]:
                raise ValueError(f"function_name key missing for stage {stage}")
