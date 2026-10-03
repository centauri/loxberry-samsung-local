"""Value-free support reports; never export the registry or raw payloads."""

import re

from . import __version__
from .capabilities import BOARD_MAP, OCF_TYPES, READ_ROOTS, readable


def report_path(path):
    return (isinstance(path, str) and (readable(path) or path in {"/oic/res", "/device/0"})
            and all(re.fullmatch(r"[A-Za-z]{1,24}|[0-9]{1,4}", p) for p in path.strip("/").split("/")))


def support_report(registry):
    devices = []
    for device in list(registry.values())[:128]:
        kind = device.get("kind")
        status = device.get("status")
        diagnostic = device.get("resource_diagnostics", {})
        reads = {}
        for path, row in diagnostic.get("reads", {}).items():
            if report_path(path) and isinstance(row, dict) and re.fullmatch(r"[245]\.\d{2}", str(row.get("code", ""))):
                reads[path] = {"code": row["code"]}
        devices.append({
            "type": kind if kind in set(OCF_TYPES.values()) | set(BOARD_MAP.values()) else "unknown",
            "status": status if status in {"online", "offline", "unsupported", "auth_required", "disabled", "discovered", "identity_mismatch", "identity_conflict"} else "unknown",
            "certificate_verified_by_readings": bool(device.get("legacy_verified")),
            "automatic_test_attempted": bool(device.get("compatibility_attempted")),
            "reads": reads,
            "mapped_resource_roots": sorted({p.split("/")[1] for p in device.get("resources", []) if isinstance(p, str) and len(p.split("/")) > 1 and p.split("/")[1] in READ_ROOTS}),
            "sensor_count": len(device.get("sensors", {})),
        })
    return {"plugin_version": __version__, "format": 1, "devices": devices,
            "privacy": "No addresses, identifiers, names, credentials, logs or reading values. Hardware compatibility is not inferred from discovery."}
