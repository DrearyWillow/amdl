import runpy
from unittest.mock import patch


def test_main_module() -> None:
    with patch("amdl.main.main") as main:
        runpy.run_module("amdl.__main__", run_name="__main__")
    main.assert_called_once_with()
