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


def test_stable_promotion_updates_both_channels(tmp_path):
    feed.publish('0.2.14', tmp_path)
    feed.publish('0.2.18', tmp_path, stable_release=True)
    assert read(tmp_path / 'release.cfg')['VERSION'] == '0.2.18'
    assert read(tmp_path / 'prerelease.cfg')['VERSION'] == '0.2.18'
    with pytest.raises(ValueError, match='backwards'):
        feed.publish('0.2.17', tmp_path, stable_release=True)
    feed.publish('0.2.19', tmp_path)
    assert read(tmp_path / 'release.cfg')['VERSION'] == '0.2.18'


def test_plugin_has_native_update_endpoints():
    cfg = read(ROOT / "plugin.cfg")
    assert cfg["AUTOMATIC_UPDATES"] == "true"
    base = "https://raw.githubusercontent.com/centauri/loxberry-samsung-local/updates/"
    assert cfg["RELEASECFG"] == base + "release.cfg"
    assert cfg["PRERELEASECFG"] == base + "prerelease.cfg"


def test_edge_uses_immutable_release_and_does_not_change_stable(tmp_path):
    feed.publish('0.2.19', tmp_path, stable_release=True)
    stable = (tmp_path / 'release.cfg').read_bytes()
    feed.publish('0.2.20', tmp_path, tag='v0.2.20-edge')
    assert (tmp_path / 'release.cfg').read_bytes() == stable
    edge = read(tmp_path / 'prerelease.cfg')
    assert edge['VERSION'] == '0.2.20'
    assert '/v0.2.20-edge/loxberry-samsung-local-0.2.20.zip' in edge['ARCHIVEURL']
    with pytest.raises(ValueError, match='channel'):
        feed.publish('0.2.20', tmp_path, stable_release=True, tag='v0.2.20-edge')
    with pytest.raises(ValueError, match='channel'):
        feed.publish('0.2.20', tmp_path, tag='edge')
