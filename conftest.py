from pathlib import Path

import pytest


def pytest_configure(config: pytest.Config) -> None:
    local_tmp = Path(__file__).parent / ".pytest_tmp"
    local_tmp.mkdir(exist_ok=True)
    config.option.basetemp = local_tmp
