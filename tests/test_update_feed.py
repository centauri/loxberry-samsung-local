import configparser
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("update_feed", ROOT / "tools/update_feed.py")
feed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(feed)


def read(path):
    cfg = configparser.ConfigParser()
    cfg.optionxform = str
    cfg.read(path)
    return cfg["AUTOUPDATE"]


def test_feed_channels_and_published_zip_urls(tmp_path):
    feed.publish("0.2.14", tmp_path)
    assert read(tmp_path / "release.cfg")["VERSION"] == "0.0.0"
    cfg = read(tmp_path / "prerelease.cfg")
    assert cfg["VERSION"] == "0.2.14"
    assert cfg["ARCHIVEURL"] == feed.REPO + "/releases/download/v0.2.14/loxberry-samsung-local-0.2.14.zip"
    assert cfg["INFOURL"] == feed.REPO + "/releases/tag/v0.2.14"
    stable = (tmp_path / "release.cfg").read_bytes()
    feed.publish("0.2.15", tmp_path)
    assert (tmp_path / "release.cfg").read_bytes() == stable
    with pytest.raises(ValueError, match="backwards"):
        feed.publish("0.2.14", tmp_path)
    assert read(tmp_path / "prerelease.cfg")["VERSION"] == "0.2.15"


def test_plugin_has_native_update_endpoints():
    cfg = read(ROOT / "plugin.cfg")
    assert cfg["AUTOMATIC_UPDATES"] == "true"
    base = "https://raw.githubusercontent.com/centauri/loxberry-samsung-local/updates/"
    assert cfg["RELEASECFG"] == base + "release.cfg"
    assert cfg["PRERELEASECFG"] == base + "prerelease.cfg"
