"""Guard the installer contract, including the pre-publication upgrade identity."""
import configparser
import importlib.util
from pathlib import Path
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("plugin_build", ROOT / "tools/build.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


@pytest.mark.parametrize("section,key", [
    ("AUTHOR", "NAME"), ("AUTHOR", "EMAIL"), ("PLUGIN", "VERSION"),
    ("PLUGIN", "NAME"), ("PLUGIN", "TITLE"), ("PLUGIN", "FOLDER"),
    ("SYSTEM", "INTERFACE"),
])
def test_missing_installer_metadata_rejected(section, key):
    cfg = configparser.ConfigParser()
    cfg.read(ROOT / "plugin.cfg")
    cfg[section][key] = ""
    with pytest.raises(ValueError, match=f"{section}.{key}"):
        builder.validate_metadata(cfg)


def test_release_packages_preserve_their_upgrade_identities(tmp_path):
    packages = []
    for legacy in (False, True):
        target = builder.build(tmp_path, legacy_identity=legacy)
        with zipfile.ZipFile(target) as archive:
            files = {name: archive.read(name) for name in archive.namelist()}
        cfg = configparser.ConfigParser()
        cfg.read_string(files["plugin.cfg"].decode("utf-8"))
        builder.validate_metadata(cfg)
        expected = (("Samsung Local Contributors", "samsung-local@localhost.invalid")
                    if legacy else ("centauri", "1310223+centauri@users.noreply.github.com"))
        assert (cfg["AUTHOR"]["NAME"], cfg["AUTHOR"]["EMAIL"]) == expected
        assert cfg["PLUGIN"]["NAME"] == cfg["PLUGIN"]["FOLDER"] == "samsunglocal"
        assert cfg["PLUGIN"]["WEBSITE"] == "https://github.com/centauri/loxberry-samsung-local"
        assert b"\r" not in files.pop("plugin.cfg")
        packages.append(files)
    # Only identity metadata differs; same code, preservation hooks and UI.
    assert packages[0] == packages[1]
