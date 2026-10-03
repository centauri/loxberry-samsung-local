"""Guard the installer contract, including exact case-sensitive key names."""
import configparser
import importlib.util
from pathlib import Path
import zipfile
import shutil
import subprocess

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
    cfg.optionxform = str
    cfg.read(ROOT / "plugin.cfg")
    cfg[section][key] = ""
    with pytest.raises(ValueError, match=f"{section}.{key}"):
        builder.validate_metadata(cfg)


def test_release_package_identity_and_exact_metadata(tmp_path):
    target = builder.build(tmp_path)
    with zipfile.ZipFile(target) as archive:
        payload = archive.read("plugin.cfg")
    cfg = configparser.ConfigParser()
    cfg.optionxform = str
    cfg.read_string(payload.decode("utf-8"))
    builder.validate_metadata(cfg)
    assert cfg["AUTHOR"]["NAME"] == "centauri"
    assert cfg["AUTHOR"]["EMAIL"] == "1310223+centauri@users.noreply.github.com"
    assert cfg["PLUGIN"]["NAME"] == cfg["PLUGIN"]["FOLDER"] == "samsunglocal"
    assert cfg["PLUGIN"]["WEBSITE"] == "https://github.com/centauri/loxberry-samsung-local"
    assert b"\r" not in payload


def test_lowercase_keys_are_rejected():
    cfg = configparser.ConfigParser()
    cfg.optionxform = str
    cfg.read_string((ROOT / "plugin.cfg").read_text().replace("NAME=", "name="))
    with pytest.raises(ValueError, match="AUTHOR.NAME"):
        builder.validate_metadata(cfg)


def test_packaged_metadata_with_loxberry_perl_parser(tmp_path):
    if not shutil.which("perl"):
        pytest.skip("Perl unavailable locally; required in Linux CI")
    target = builder.build(tmp_path)
    with zipfile.ZipFile(target) as archive:
        archive.extract("plugin.cfg", tmp_path)
    # Config::Simple is the parser used by LoxBerry sbin/plugininstall.pl.
    script = r'''use Config::Simple;
my $cfg = Config::Simple->new($ARGV[0]) or die Config::Simple->error();
for my $key (qw(AUTHOR.NAME AUTHOR.EMAIL PLUGIN.VERSION PLUGIN.NAME
                PLUGIN.TITLE PLUGIN.FOLDER SYSTEM.INTERFACE PLUGIN.WEBSITE)) {
    die "Missing $key" unless $cfg->param($key);
}
die "Wrong author" unless $cfg->param("AUTHOR.NAME") eq "centauri";
'''
    subprocess.run(["perl", "-e", script, str(tmp_path / "plugin.cfg")],
                   check=True, capture_output=True, text=True)
