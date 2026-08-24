import importlib

from amdl import json_type


def test_json_type() -> None:
    importlib.reload(json_type)
