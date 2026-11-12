"""Read the versioned runtime defaults without sharing mutable dictionaries."""

import json
from importlib.resources import files


def load_defaults():
    return json.loads(files("cybersprite").joinpath("data", "pipeline_defaults.json").read_bytes())
