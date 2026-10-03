"""Write native LoxBerry manifests after the matching release ZIP is published."""
import argparse
import configparser
from pathlib import Path
import re

REPO = "https://github.com/centauri/loxberry-samsung-local"


def manifest(version, archive_version=None):
    archive_version = archive_version or version
    return (f"[AUTOUPDATE]\nVERSION={version}\n"
            f"ARCHIVEURL={REPO}/releases/download/v{archive_version}/"
            f"loxberry-samsung-local-{archive_version}.zip\n"
            f"INFOURL={REPO}/releases/tag/v{archive_version}\n")


def publish(version, directory):
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Expected a numeric three-part plugin version")
    directory.mkdir(parents=True, exist_ok=True)
    prerelease = directory / "prerelease.cfg"
    if prerelease.exists():
        cfg = configparser.ConfigParser()
        cfg.optionxform = str
        cfg.read(prerelease)
        previous = cfg["AUTOUPDATE"]["VERSION"]
        if tuple(map(int, previous.split('.'))) > tuple(map(int, version.split('.'))):
            raise ValueError("Refusing to move the update feed backwards")
    prerelease.write_text(manifest(version), encoding="utf-8", newline="\n")
    stable = directory / "release.cfg"
    if not stable.exists():
        # No stable release yet: 0.0.0 cannot update an installed plugin.
        # Keep URLs valid, but do not advertise evaluation builds as stable.
        stable.write_text(manifest("0.0.0", version), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("version")
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    publish(args.version, args.directory)
