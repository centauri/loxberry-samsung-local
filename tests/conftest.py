import pytest
from samsung_local.storage import Paths


@pytest.fixture
def paths(tmp_path):
    return Paths(tmp_path / "config", tmp_path / "data", tmp_path / "log")
