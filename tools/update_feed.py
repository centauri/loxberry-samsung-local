"""Write native LoxBerry manifests after the matching release ZIP is published."""
import argparse
import configparser
from pathlib import Path
import re

REPO = "https://github.com/centauri/loxberry-samsung-local"


def manifest(version, archive_version=None, tag=None):
    archive_version = archive_version or version
    tag = tag or f"v{archive_version}"
    return (f"[AUTOUPDATE]\nVERSION={version}\n"
            f"ARCHIVEURL={REPO}/releases/download/{tag}/"
            f"loxberry-samsung-local-{archive_version}.zip\n"
            f"INFOURL={REPO}/releases/tag/{tag}\n")


def publish(version, directory, stable_release=False, tag=None):
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Expected a numeric three-part plugin version")
    tag = tag or f"v{version}"
    if tag not in {f"v{version}", f"v{version}-edge"} or (stable_release and tag.endswith('-edge')):
        raise ValueError("Release tag does not match version/channel")
    directory.mkdir(parents=True, exist_ok=True)
    prerelease = directory / "prerelease.cfg"
    stable = directory / "release.cfg"
    for channel in ([prerelease, stable] if stable_release else [prerelease]):
        if not channel.exists():
            continue
        cfg = configparser.ConfigParser()
        cfg.optionxform = str
        cfg.read(channel)
        previous = cfg["AUTOUPDATE"]["VERSION"]
        if tuple(map(int, previous.split('.'))) > tuple(map(int, version.split('.'))):
            raise ValueError("Refusing to move the update feed backwards")
    prerelease.write_text(manifest(version, tag=tag), encoding="utf-8", newline="\n")
    if stable_release:
        stable.write_text(manifest(version), encoding="utf-8", newline="\n")
    elif not stable.exists():
        # No stable release yet: 0.0.0 cannot update an installed plugin.
        # Keep URLs valid, but do not advertise evaluation builds as stable.
        stable.write_text(manifest("0.0.0", version), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("version")
    parser.add_argument("directory", type=Path)
    parser.add_argument("--stable", action="store_true")
    parser.add_argument("--tag")
    args = parser.parse_args()
    publish(args.version, args.directory, stable_release=args.stable, tag=args.tag)
