import os
import yaml

class Config:
    def __init__(self, config_file="config.yaml"):
        possible_paths = [
            config_file,
            os.path.join(os.path.dirname(__file__), config_file),
            os.path.join(os.getcwd(), config_file)
        ]
        for path in possible_paths:
            if os.path.exists(path):
                config_file = path
                break
        else:
            raise FileNotFoundError(f"Config file {config_file} not found in any standard location.")
        with open(config_file, "r") as f:
            self.cfg = yaml.safe_load(f)
        self.__file__ = config_file

    def _get_config_value(self, key, default=None):
        keys = key.split('.')
        d = self.cfg
        for k in keys:
            d = d.get(k)
            if d is None:
                return default
        return d

    def get_path(self, key, default=None):
        value = self._get_config_value(key, default)
        if value:
            return os.path.normpath(value)
        return default

config = None
try:
    config = Config()
except Exception as e:
    print("WARNING: Failed to load config.yaml. Reason:", e)
