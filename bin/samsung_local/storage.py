"""Atomic private storage. Configuration and credentials never enter the web root."""

import ipaddress
import copy
import json
import os
import re
import tempfile
from pathlib import Path

DEFAULTS = {"schema": 1, "enabled": True, "poll_seconds": 30, "scan_seconds": 600,
            "networks": [], "devices": {}, "language": "en"}


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=True, allow_nan=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def valid_key(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9-]{1,80}", value):
        raise ValueError("Invalid device identifier")
    return value


def validate_config(raw):
    if not isinstance(raw, dict) or raw.get("schema", 1) != 1:
        raise ValueError("Unsupported configuration version")
    result = copy.deepcopy(dict(DEFAULTS, **raw))
    if result['language'] not in ('en', 'nl'):
        raise ValueError('Unsupported interface language')
    if type(result["enabled"]) is not bool:
        raise ValueError("Enabled must be true or false")
    for key, low, high in (("poll_seconds", 15, 3600), ("scan_seconds", 120, 86400)):
        if type(result[key]) is not int or not low <= result[key] <= high:
            raise ValueError(f"{key} must be between {low} and {high}")
    if not isinstance(result["networks"], list) or len(result["networks"]) > 8:
        raise ValueError("Use at most eight IPv4 networks")
    networks = []
    for item in result["networks"]:
        net = ipaddress.ip_network(item, strict=False)
        if net.version != 4 or not net.is_private or net.is_loopback or net.prefixlen < 22:
            raise ValueError("Scan networks must be private IPv4 /22 or smaller")
        networks.append(str(net))
    if sum(ipaddress.ip_network(n).num_addresses for n in networks) > 1024:
        raise ValueError("At most 1024 scan addresses in total")
    result["networks"] = networks
    if not isinstance(result["devices"], dict) or len(result["devices"]) > 128:
        raise ValueError("Invalid device settings")
    for key, options in result["devices"].items():
        valid_key(key)
        if not isinstance(options, dict) or any(k not in {"enabled", "control"} for k in options):
            raise ValueError("Invalid device options")
        if any(type(v) is not bool for v in options.values()):
            raise ValueError("Device options must be true or false")
    return result


class Paths:
    def __init__(self, config, data, log):
        self.config, self.data, self.log = map(Path, (config, data, log))
        for path in (self.config, self.data, self.log, self.config / "credentials"):
            path.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.settings = self.config / "settings.json"
        self.registry = self.config / "devices.json"
        self.status = self.data / "status.json"
        self.requests = self.data / "requests"
        self.requests.mkdir(exist_ok=True, mode=0o700)

    def load_config(self):
        return validate_config(read_json(self.settings, DEFAULTS))
