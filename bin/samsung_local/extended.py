"""Read-only capability mappings derived from LocalThings (MIT).

Copyright (c) 2026 Marc Billow. See licenses/LocalThings-LICENSE.
Only reviewed fields are exported; never flatten arbitrary appliance payloads.
"""

import math
import re

P = "x.com.samsung.da."
# Names are protocol fields, not model numbers. Units are only assigned below
# when the wire format or the upstream mapping establishes their meaning.
FIELDS = {
    "airflow": "speed direction speedLevel",
    "wind": "horizontal vertical horizontalAngle verticalAngle horizontalSwingMode modes",
    "mode": "workingMode modes",
    "operational": "currentJobState currentMachineState remainingTime progressPercentage progressPercentageDrying progressPercentageWashing remainingWashTime operationTime",
    "door": "openState", "doors": "openState", "kimchidoors": "openState",
    "temperatures": "current desired desiredHeat", "temperature": "current desired",
    "humidity": "desiredHumidity",
    "filter": "filterStatus",
    "energy": "battery charging",
    "water": "cumulativeWater",
    "refrigeration": "rapidCool rapidFreeze rapidFreezing rapidFridge defrost",
    "icemaker": "status iceMaker iceMaker.state iceMaker.iceMakingStatus",
    "washer": "waterTemperature spinLevel rinseCycles soilLevel dryLevel dryTime washTime wrinklePrevent detergentLevel softenerLevel autoDetergentEnabled autoSoftenerEnabled",
    "dishwasher": "heatedDry highTemperatureDry rinseLevel sanitize selectedZone speedBooster",
    "oven": "state operation subOperation powerLevel",
    "cooktop": "power childLock operationState operationBurnerNumber",
    "cooktopmonitoring": "cooktopRunningState warmingCenterState",
    "hood": "fanSpeed lamp frontVent hood.fanSpeed",
    "watertank": "status waterfullAlarmStatus",
    "component": "status dustbagUsage",
    "status": "status stickStatus stickbattery stickcleaningstatus stickoperationmode filterDoorStatus filterCleanRemainTime",
    "consumable": "state",
    "runningmode": "runningMode", "runn": "runningMode",
    "airdresseroption": "sanitize", "modeoption": "windfree windsleep",
}
READ_ROOTS = set(FIELDS) | {"sensors", "alarms"}


def scalar(value):
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)) and math.isfinite(value):
        return value
    if isinstance(value, str) and len(value) <= 160 and not any(ord(c) < 32 for c in value):
        return value
    return None


def temperature_unit(rep):
    raw = str(rep.get("units", rep.get(P + "unit", ""))).upper()
    return "C" if raw in {"C", "CELSIUS"} else "F" if raw in {"F", "FAHRENHEIT"} else None


def mapped_readings(href, rep, kind="unknown"):
    """Yield (topic suffix, scalar, field path, unit), with bounded arrays."""
    root = href.split("/")[1]
    slug = href.strip("/").replace("/", "_")
    rows = [("", rep)]
    items = rep.get(P + "items", [])
    if root in {"temperatures", "doors", "consumable"} and isinstance(items, list):
        seen = set()
        for item in items[:32]:
            if not isinstance(item, dict):
                continue
            item_id = str(item.get(P + "id", ""))
            # Numeric protocol IDs are stable across list reordering. Do not use
            # appliance descriptions or user-defined names as MQTT topic parts.
            if not re.fullmatch(r"[0-9]{1,4}", item_id) or item_id in seen:
                continue
            seen.add(item_id)
            rows.append(("item_" + item_id + "_", item))
    for label, row in rows:
        for short in FIELDS.get(root, "").split():
            for field in (short, P + short):
                value = row.get(field)
                if short == "modes" and isinstance(value, list):
                    # Preserve all current modes, not only the first mode.
                    value = ",".join(v for v in value[:16] if isinstance(v, str) and len(v) < 64)
                value = scalar(value)
                if value is None:
                    continue
                unit = temperature_unit(row) if root in {"temperatures", "temperature"} else None
                if short.startswith("progressPercentage") or short == "desiredHumidity":
                    unit = "%"
                yield slug + "_" + label + short.replace(".", "_"), value, label + field, unit
    if root == "sensors" and isinstance(items, list):
        for item in items[:32]:
            if not isinstance(item, dict):
                continue
            typ = item.get(P + "type")
            names = {"Dust": "dust", "FineDust": "fine_dust", "SuperFineDust": "super_fine_dust",
                     "CO2": "co2", "Odor": "odor", "CleanLevel": "clean_level"}
            if typ not in names:
                continue
            values = item.get(P + "value")
            if not isinstance(values, list) or not values:
                continue
            try:
                value = float(values[0])
            except (TypeError, ValueError):
                continue
            if not math.isfinite(value) or value < 0:
                continue
            # AC boards use family-dependent particulate scaling. Do not assign
            # purifier units to them just because the field name matches.
            unit = "ppm" if typ == "CO2" else "ug/m3" if (
                typ in {"Dust", "FineDust", "SuperFineDust"} and kind in {"air_purifier", "air_monitor"}) else None
            yield slug + "_" + names[typ], value, P + "items." + typ, unit
    if root == "alarms" and isinstance(items, list):
        codes = []
        for item in items[:32]:
            if not isinstance(item, dict):
                continue
            code = item.get(P + "code")
            if (isinstance(code, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", code)
                    and not code.lower().endswith("_off") and str(item.get(P + "state", "")).lower() != "deleted"):
                codes.append(code)
        yield slug + "_active", ",".join(sorted(set(codes))) or "none", P + "items.code", None
