"""LocalThings-shaped diagnostic data; no Home Assistant runtime required.

Redaction and CBOR encoding are vendored unchanged from LocalThings (MIT).
Additional filtering omits security/network resources and local identifiers.
This is a partial adapter capture, not a Home Assistant diagnostics download.
"""
from importlib.metadata import PackageNotFoundError, version
import re

from . import __version__
from .capabilities import normalize, readable, safe_href
from .vendor.localthings.encode import json_safe
from .vendor.localthings.redact import REDACTED, redact_resources

REVISION = '5c2e185ec5912b29407934897d8d888aa4cfc374'
BLOCKED = {'sec', 'security', 'ownership', 'wirelessinfo', 'configuration', 'file',
           'coapcloudconfresuri', 'wificonfresuri', 'easysetupresuri', 'devconfresuri'}
PRIVATE = re.compile(r'credential|certificate|privatekey|owner|address|endpoint', re.I)
IDENTIFIER = re.compile(r'[0-9a-f]{8}-[0-9a-f-]{27}|(?:\d{1,3}\.){3}\d{1,3}|(?:[0-9a-f]{2}:){5}[0-9a-f]{2}', re.I)


def bounded(value, depth=0):
    """Bound public evidence and remove identifiers outside upstream key rules."""
    if depth > 12:
        return {'adapter_truncated': True}
    if isinstance(value, dict):
        return {IDENTIFIER.sub('REDACTED', str(k))[:240]:
                REDACTED if PRIVATE.search(str(k)) or k in {'di', 'pi', 'id', 'eps', 'ep'}
                else bounded(v, depth + 1) for k, v in list(value.items())[:256]}
    if isinstance(value, (list, tuple)):
        return [bounded(v, depth + 1) for v in value[:256]]
    if isinstance(value, str):
        return IDENTIFIER.sub('REDACTED', value[:2048])
    if isinstance(value, (bytes, bytearray, memoryview)):
        return REDACTED
    return value


def allowed(href):
    return safe_href(href) and not set(href.lower().split('/')) & BLOCKED


def capture(device, batch, info, kind):
    resources = {}
    for entry in batch[:256] if isinstance(batch, list) else []:
        if not isinstance(entry, dict):
            continue
        href, rep = entry.get('href'), entry.get('rep')
        if allowed(href) and isinstance(rep, dict):
            resources[href] = rep
    if info:
        resources['/information/vs/0'] = info
    unbound = [h for h, rep in resources.items() if h != '/information/vs/0'
               and (not readable(h) or not normalize({h: rep}, kind)[0])]
    # Do not claim HA bindings, discovery probes or subdevices we never collected.
    return json_safe(bounded(redact_resources({
        'device_type': kind,
        'resources': resources,
        'identity': {'manufacturer': device.get('mnmn'), 'model': device.get('mnmo'),
                     'device_types': device.get('rt', []), 'resources': {'/oic/d': device}},
        'unbound_hrefs': sorted(unbound),
    })))


def envelope(data):
    try:
        protocol_version = version('smartthings-local')
    except PackageNotFoundError:
        protocol_version = 'unavailable'
    return {'data': dict(data, smartthings_local_version=protocol_version),
            'adapter': {'name': 'loxberry-samsung-local', 'version': __version__,
                        'localthings_reference': REVISION,
                        'capture_scope': 'Partial existing reads; no extra probes. No HA entities or subdevice enumeration.',
                        'redaction': 'LocalThings rules plus identifier/security filtering and size limits. Review all values before sharing.',
                        'unbound_meaning': 'No adapter reading mapped at this href; not a LocalThings coverage result.'}}
