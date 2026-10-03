"""Reviewed capability mappings adapted from mbillow/localthings (MIT).

Copyright (c) 2026 Marc Billow. See licenses/LocalThings-LICENSE.
Never infer write support from a field's presence alone.
"""

import math
import re

from .extended import READ_ROOTS as EXTENDED_ROOTS, mapped_readings

PREFIX = "x.com.samsung.da."
READ_ROOTS = {"power", "temperature", "humidity", "operational", "energy", "water",
              "kidslock", "remotectrl", "mode", "door", "filter", "airquality", "fanspeed"}


READ_ROOTS |= EXTENDED_ROOTS


def safe_href(href):
    if not isinstance(href, str) or len(href) > 240:
        return False
    return bool(re.fullmatch(r"/[A-Za-z0-9_/-]+", href)) and not any(
        part in {"sec", "security", "ownership"} for part in href.lower().split("/"))


def readable(href):
    return safe_href(href) and href.split("/")[1] in READ_ROOTS


def directory_links(value):
    """Both legacy list-of-device directories and OCF 1.x links objects."""
    found = set()
    def walk(node, depth=0):
        if depth > 12 or len(found) >= 256:
            return
        if isinstance(node, dict):
            href = node.get("href")
            if safe_href(href):
                found.add(href)
            for key in ("links", "rep"):
                walk(node.get(key), depth + 1)
        elif isinstance(node, list):
            for item in node[:256]:
                walk(item, depth + 1)
    walk(value)
    return sorted(found)


def batch_resources(value):
    """Extract only supported representations from Samsung's /device/0 batch.

    Shape follows LocalThings registry/batch.py (MIT, notice above). Never
    retain security resources or expose the entire batch as diagnostics.
    """
    result = {}
    if not isinstance(value, list):
        return result
    for entry in value[:256]:
        if not isinstance(entry, dict):
            continue
        href, rep = entry.get("href"), entry.get("rep")
        if (readable(href) or href == "/information/vs/0") and isinstance(rep, dict):
            if rep and set(rep) != {"href"}:
                result[href] = rep
    return result


BOARD_MAP = {'REF': 'refrigerator',
 'RAC': 'airconditioner',
 'PRAC': 'airconditioner',
 'KRAC': 'airconditioner',
 'WAC': 'airconditioner',
 'FAC': 'airconditioner',
 'CAWW': 'airconditioner',
 'CAC': 'airconditioner',
 'DUCT': 'airconditioner',
 'RHS': 'airconditioner',
 'ARA': 'airconditioner',
 'DHM': 'dehumidifier',
 'EHS': 'heat_pump',
 'TVTL': 'air_purifier',
 'VTWW': 'air_purifier',
 'AVT': 'air_purifier',
 'AIR': 'air_purifier',
 'WATERPURIFIER': 'water_purifier',
 'ADW': 'dishwasher',
 'AHD': 'range_hood',
 'RANGE': 'range',
 'OVEN': 'oven',
 'MICROWAVE': 'microwave',
 'COOKTOP': 'cooktop',
 'CT': 'cooktop',
 'VSKR': 'vacuum_station',
 'DF': 'air_dresser',
 'VSWW': 'vacuum_station',
 'ASM': 'air_monitor'}
OCF_TYPES = {'oic.d.airconditioner': 'airconditioner',
 'oic.d.airpurifier': 'air_purifier',
 'oic.d.cooktop': 'cooktop',
 'oic.d.dishwasher': 'dishwasher',
 'oic.d.dryer': 'dryer',
 'oic.d.microwave': 'microwave',
 'oic.d.oven': 'oven',
 'oic.d.range': 'range',
 'oic.d.refrigerator': 'refrigerator',
 'oic.d.krefrigerator': 'refrigerator',
 'oic.d.washer': 'washer',
 'x.com.st.d.airqualitysensor': 'air_monitor',
 'x.com.st.d.dehumidifier': 'dehumidifier',
 'x.com.st.d.hood': 'range_hood',
 'x.com.st.d.microfiberfilter': 'washer',
 'x.com.st.d.stickcleaner': 'vacuum_station',
 'x.com.st.d.steamcloset': 'air_dresser',
 'x.com.st.d.winecellar': 'refrigerator',
 'oic.d.tv': 'television',
 'oic.d.networkaudio': 'network_audio',
 'oic.d.robotcleaner': 'vacuum'}

OCF_TYPES.update({"oic.d.dehumidifier": "dehumidifier", "oic.d.waterpurifier": "water_purifier"})


def device_type(rt, info):
    for item in rt if isinstance(rt, (list, tuple)) else []:
        if isinstance(item, str) and item in OCF_TYPES:
            return OCF_TYPES[item]
    for field, separator in (("modelNum", "|"), ("description", "/")):
        tokens = re.split(r"[^A-Z0-9]+", str(info.get(PREFIX + field, "")).split(separator)[0].upper())
        if "WATERPURIFIER" in tokens:
            return "water_purifier"
        for token in tokens:
            if token in BOARD_MAP:
                return BOARD_MAP[token]
    description = str(info.get(PREFIX + "description", "")).split("/", 1)[0]
    for token in reversed(description.upper().split("_")):
        for prefix, kind in (("WW", "washer"), ("WD", "washer"), ("WF", "washer"),
                             ("WV", "washer"), ("WA", "washer"), ("DV", "dryer"), ("DW", "dishwasher")):
            if re.match(prefix + (r"[EG]?\d" if prefix == "DV" else r"\d"), token):
                return kind
    return "unknown"


def boolean(value):
    if value is True or str(value).lower() in {"on", "true", "1", "locked"}:
        return 1
    if value is False or str(value).lower() in {"off", "false", "0", "unlocked"}:
        return 0
    return None


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def normalize(resources, kind="unknown"):
    """Return scalar MQTT state and the discovered sensor metadata."""
    state, sensors = {}, {}
    def add(name, value, href, field, unit=None):
        if value is not None:
            state[name] = value
            sensors[name] = {"href": href, "field": field, "unit": unit, "writable": False}
    for root, name, vendor in (("power", "power", "power"), ("kidslock", "child_lock", "kidsLock"),
                               ("remotectrl", "remote_control", "remoteControlEnabled")):
        href = f"/{root}/0" if f"/{root}/0" in resources else f"/{root}/vs/0"
        field = "value" if href == f"/{root}/0" else PREFIX + vendor
        value = boolean(resources.get(href, {}).get(field))
        if value is None:
            href, field = f"/{root}/vs/0", PREFIX + vendor
            value = boolean(resources.get(href, {}).get(field))
        add(name, value, href, field)
    for href, rep in resources.items():
        if not readable(href) or not isinstance(rep, dict):
            continue
        for name, value, field, unit in mapped_readings(href, rep, kind):
            add(name, value, href, field, unit)
        slug = href.strip("/").replace("/", "_")
        if href.startswith("/temperature/"):
            raw_unit = str(rep.get("units", rep.get(PREFIX + "unit", ""))).upper()
            unit = "C" if raw_unit.startswith("C") else "F" if raw_unit.startswith("F") else None
            for field in ("temperature", PREFIX + "temperature", PREFIX + "desiredTemperature"):
                add(slug + "_" + field.split(".")[-1], number(rep.get(field)), href, field, unit)
        for field, suffix, unit in (
            ("humidity", "humidity", "%"), (PREFIX + "humidity", "humidity", "%"),
            (PREFIX + "instantaneousPower", "power_w", "W"),
            (PREFIX + "cumulativePower", "energy_wh", "Wh"),
            (PREFIX + "filterUsage", "filter_used_percent", "%"),
        ):
            value = number(rep.get(field))
            if field == PREFIX + "cumulativePower":
                wire_unit = rep.get(PREFIX + "cumulativeUnit", "Wh")
                value = value * 1000 if value is not None and wire_unit == "kWh" else value
                if wire_unit not in {"Wh", "kWh"} or value == 0:
                    value = None
            if field == PREFIX + "instantaneousPower" and rep.get(PREFIX + "instantaneousPowerUnit", "W") != "W":
                value = None
            if field == PREFIX + "filterUsage" and value is not None and value > 100:
                value = None
            if value is not None and value >= 0:
                add(slug + "_" + suffix, value, href, field, unit)
        for field in ("machineState", "jobState", "openState", "mode", PREFIX + "state",
                      PREFIX + "progress", PREFIX + "remainingTime", PREFIX + "mode"):
            value = rep.get(field)
            if isinstance(value, str) and len(value) <= 160:
                add(slug + "_" + field.split(".")[-1], value, href, field)
    return state, sensors


def power_command(kind, resources, value):
    """MVP: opt-in power only on AC/purifier. No laundry/cooking/lock writes."""
    if kind not in {"airconditioner", "air_purifier"} or value not in {"on", "off"}:
        raise ValueError("Power control is only supported for air conditioners and air purifiers")
    remote = resources.get("/remotectrl/0", {}).get("value")
    if remote is None:
        remote = resources.get("/remotectrl/vs/0", {}).get(PREFIX + "remoteControlEnabled")
    if boolean(remote) == 0:
        raise ValueError("The appliance reports remote control disabled")
    if "/power/0" in resources and type(resources["/power/0"].get("value")) is bool:
        return "/power/0", {"value": value == "on"}
    if resources.get("/power/vs/0", {}).get(PREFIX + "power") in {"On", "Off"}:
        return "/power/vs/0", {PREFIX + "power": "On" if value == "on" else "Off"}
    raise ValueError("No supported power resource was successfully read")
